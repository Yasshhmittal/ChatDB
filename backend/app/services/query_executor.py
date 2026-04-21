"""
Query Executor Service.
Executes validated SQL queries against user's SQLite database.
Includes the correction loop: if SQL fails, retries via LLM.

Supports:
- SELECT queries (read-only connection, returns rows)
- DML queries: INSERT, UPDATE, DELETE (read-write connection, returns affected rows)
- DDL queries: CREATE, DROP, ALTER, TRUNCATE (read-write connection, returns success message)
"""

from __future__ import annotations

import sqlite3

from app.config import settings
from app.utils.database import get_read_connection, get_readwrite_connection
from app.services.sql_validator import validate_sql, get_query_type, UnsafeQueryError
from app.services.llm_service import llm_service


# Query types that return row data
_SELECT_TYPES = {"SELECT"}

# Query types that modify data and return affected row count
_DML_TYPES = {"INSERT", "UPDATE", "DELETE"}

# Query types that modify schema structure
_DDL_TYPES = {"CREATE", "DROP", "ALTER", "TRUNCATE"}


async def execute_with_retry(
    session_id: str,
    sql: str,
    schema_tables: list[dict],
    question: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Execute SQL with automatic correction loop.

    Flow:
    1. Validate SQL
    2. Detect query type and execute with appropriate connection
    3. If error → send error+SQL back to LLM → retry (up to MAX_RETRY_ATTEMPTS)
    4. Return results or final error

    Returns:
        dict with: sql, results, columns, row_count, error, retries_used, query_type, affected_rows
    """
    max_retries = settings.MAX_RETRY_ATTEMPTS
    current_sql = sql
    last_error = None
    retries = 0

    for attempt in range(1 + max_retries):  # 1 initial + N retries
        # ── Step 1: Validate ──
        try:
            validated_sql = validate_sql(current_sql, session_id)
        except UnsafeQueryError as e:
            if attempt < max_retries:
                # Ask LLM to fix unsafe query
                error_context = f"Query: {current_sql}\nValidation Error: {str(e)}"
                result = await llm_service.generate_sql(
                    schema_tables=schema_tables,
                    question=question,
                    chat_history=chat_history,
                    error_context=error_context,
                )
                current_sql = result.get("sql", "")
                retries += 1
                continue
            else:
                return {
                    "sql": current_sql,
                    "results": [],
                    "columns": [],
                    "row_count": 0,
                    "error": f"Query validation failed: {str(e)}",
                    "retries_used": retries,
                    "query_type": "UNKNOWN",
                    "affected_rows": 0,
                }

        # ── Step 2: Detect query type and execute ──
        query_type = get_query_type(validated_sql)

        try:
            if query_type in _SELECT_TYPES:
                results, columns = _execute_select(session_id, validated_sql)
                return {
                    "sql": validated_sql,
                    "results": results,
                    "columns": columns,
                    "row_count": len(results),
                    "error": None,
                    "retries_used": retries,
                    "query_type": query_type,
                    "affected_rows": 0,
                }
            elif query_type in _DML_TYPES:
                affected = _execute_write(session_id, validated_sql)
                return {
                    "sql": validated_sql,
                    "results": [],
                    "columns": [],
                    "row_count": 0,
                    "error": None,
                    "retries_used": retries,
                    "query_type": query_type,
                    "affected_rows": affected,
                }
            elif query_type in _DDL_TYPES:
                _execute_write(session_id, validated_sql)
                return {
                    "sql": validated_sql,
                    "results": [],
                    "columns": [],
                    "row_count": 0,
                    "error": None,
                    "retries_used": retries,
                    "query_type": query_type,
                    "affected_rows": 0,
                }
            else:
                return {
                    "sql": validated_sql,
                    "results": [],
                    "columns": [],
                    "row_count": 0,
                    "error": f"Unsupported query type: {query_type}",
                    "retries_used": retries,
                    "query_type": query_type,
                    "affected_rows": 0,
                }
        except sqlite3.Error as e:
            last_error = str(e)
            if attempt < max_retries:
                # Send error back to LLM for correction
                error_context = (
                    f"Query: {current_sql}\n"
                    f"SQLite Error: {last_error}"
                )
                result = await llm_service.generate_sql(
                    schema_tables=schema_tables,
                    question=question,
                    chat_history=chat_history,
                    error_context=error_context,
                )
                current_sql = result.get("sql", "")
                retries += 1
            else:
                return {
                    "sql": current_sql,
                    "results": [],
                    "columns": [],
                    "row_count": 0,
                    "error": f"Query execution failed after {retries} retries: {last_error}",
                    "retries_used": retries,
                    "query_type": query_type,
                    "affected_rows": 0,
                }

    # Should not reach here, but safety net
    return {
        "sql": current_sql,
        "results": [],
        "columns": [],
        "row_count": 0,
        "error": f"Max retries exceeded. Last error: {last_error}",
        "retries_used": retries,
        "query_type": "UNKNOWN",
        "affected_rows": 0,
    }


def _execute_select(session_id: str, sql: str) -> tuple[list[dict], list[str]]:
    """
    Execute a validated SELECT query in read-only mode.

    Returns:
        (list_of_row_dicts, column_names)
    """
    with get_read_connection(session_id) as conn:
        cursor = conn.execute(sql)

        # Get column names
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Fetch with row limit
        rows = cursor.fetchmany(settings.MAX_RESULT_ROWS)

        # Convert to list of dicts
        results = [dict(zip(columns, row)) for row in rows]

    return results, columns


def _execute_write(session_id: str, sql: str) -> int:
    """
    Execute a validated DML/DDL query with a read-write connection.

    Returns:
        Number of affected rows (for DML). 0 for DDL.
    """
    with get_readwrite_connection(session_id) as conn:
        cursor = conn.execute(sql)
        return cursor.rowcount if cursor.rowcount >= 0 else 0
