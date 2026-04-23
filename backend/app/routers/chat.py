"""
Chat Router — Natural language to SQL query endpoint.
Orchestrates: RAG filter → LLM → Validator → Executor → Chart → Response
"""

import time
from fastapi import APIRouter, HTTPException, Depends

from app.models import ChatRequest, ChatResponse, ChartConfig
from app.utils.database import db_exists, has_modified_db
from app.services.rag_filter import get_relevant_tables
from app.services.llm_service import llm_service
from app.services.query_executor import execute_with_retry
from app.services.chart_service import detect_chart
from app.routers.auth import get_current_user_or_none
from app.auth_db import increment_guest_query, log_query, update_last_active, touch_user_session


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict | None = Depends(get_current_user_or_none)):
    """
    Ask a natural language question about your database.

    Flow:
    1. RAG filter → find relevant tables
    2. LLM → generate SQL + explanation (single call)
    3. Validate SQL → execute with retry loop
    4. Detect chart type (rule-based, no LLM) — only for SELECT
    5. Return everything: SQL, results, explanation, chart
    """
    # ── Track execution time ──
    start_time = time.time()

    # ── Validate session ──
    if not db_exists(request.session_id):
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload a database file first.",
        )

    # ── Rate Limit Check ──
    user_id = None
    if current_user:
        user_id = int(current_user["id"])
        update_last_active(user_id)
    else:
        count = increment_guest_query(request.session_id)
        if count > 5:
            raise HTTPException(
                status_code=403,
                detail="Guest query limit reached (5/5). Please sign in to continue querying your data."
            )


    # ── Step 1: RAG — find relevant tables ──
    try:
        relevant_tables = get_relevant_tables(
            session_id=request.session_id,
            question=request.question,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze schema: {str(e)}",
        )

    if not relevant_tables:
        raise HTTPException(
            status_code=400,
            detail="No tables found in database. Please upload data first.",
        )

    # ── Step 2: LLM — generate SQL + explanation (SINGLE call) ──
    try:
        llm_result = await llm_service.generate_sql(
            schema_tables=relevant_tables,
            question=request.question,
            chat_history=[msg.model_dump() for msg in request.chat_history],
        )
    except RuntimeError as e:
        # No LLM provider available
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM generation failed: {str(e)}",
        )

    sql_query = llm_result.get("sql", "")
    explanation = llm_result.get("explanation", "")

    if not sql_query:
        # Log failed generation
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_query(
            session_id=request.session_id,
            question=request.question,
            generated_sql="",
            was_successful=False,
            error_message="No SQL query generated",
            execution_time_ms=elapsed_ms,
            user_id=user_id,
        )
        return ChatResponse(
            question=request.question,
            explanation=explanation or "I couldn't generate a SQL query for this question. Please try rephrasing.",
            error="No SQL query generated.",
        )

    # ── Step 3: Validate + Execute (with correction loop) ──
    exec_result = await execute_with_retry(
        session_id=request.session_id,
        sql=sql_query,
        schema_tables=relevant_tables,
        question=request.question,
        chat_history=[msg.model_dump() for msg in request.chat_history],
    )

    # ── Step 4: Chart detection (rule-based, instant) — only for SELECT ──
    chart_config = None
    query_type = exec_result.get("query_type", "SELECT")
    if query_type == "SELECT" and exec_result["results"] and exec_result["columns"]:
        chart_data = detect_chart(
            columns=exec_result["columns"],
            data=exec_result["results"],
        )
        if chart_data:
            chart_config = ChartConfig(**chart_data)

    # ── Step 5: Log query to history ──
    elapsed_ms = int((time.time() - start_time) * 1000)
    was_successful = not bool(exec_result.get("error"))
    try:
        log_query(
            session_id=request.session_id,
            question=request.question,
            generated_sql=exec_result["sql"],
            query_type=query_type,
            row_count=exec_result["row_count"],
            execution_time_ms=elapsed_ms,
            retries_used=exec_result.get("retries_used", 0),
            was_successful=was_successful,
            error_message=exec_result.get("error"),
            user_id=user_id,
        )
        # Touch the session's last_accessed_at
        touch_user_session(request.session_id)
    except Exception as e:
        print(f"[WARN] Failed to log query: {e}")

    # ── Step 6: Build response ──
    # Add assumptions to explanation if present
    full_explanation = explanation
    assumptions = llm_result.get("assumptions", "")
    if assumptions:
        full_explanation += f"\n\n📝 Assumptions: {assumptions}"

    # For write operations, note that a copy was used
    if query_type != "SELECT" and not exec_result.get("error"):
        full_explanation += "\n\n🔒 Your original data is preserved. Changes were applied to a separate copy that you can download."

    return ChatResponse(
        question=request.question,
        sql_query=exec_result["sql"],
        results=exec_result["results"],
        columns=exec_result["columns"],
        row_count=exec_result["row_count"],
        explanation=full_explanation,
        chart=chart_config,
        error=exec_result.get("error"),
        retries_used=exec_result.get("retries_used", 0),
        query_type=query_type,
        affected_rows=exec_result.get("affected_rows", 0),
    )
