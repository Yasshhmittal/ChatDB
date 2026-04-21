"""
Schema Router — Database schema exploration endpoints.
Lets the frontend display table structure and sample data.
"""

from typing import Any
from fastapi import APIRouter, HTTPException

from app.models import SchemaResponse, TableInfo, ColumnInfo, SampleDataResponse
from app.utils.database import db_exists
from app.services.schema_extractor import extract_schema

router = APIRouter()


@router.get("/schema/{session_id}", response_model=SchemaResponse)
async def get_schema(session_id: str):
    """Get full schema (tables + columns) for a session's database."""
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        schema = extract_schema(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    tables = [
        TableInfo(
            name=t["name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count", 0),
        )
        for t in schema
    ]

    return SchemaResponse(session_id=session_id, tables=tables)


@router.get("/schema/{session_id}/sample/{table_name}", response_model=SampleDataResponse)
async def get_sample_data(session_id: str, table_name: str):
    """Get sample rows (first 10) from a specific table."""
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        schema = extract_schema(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Find the requested table
    table = next((t for t in schema if t["name"] == table_name), None)
    if not table:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found.",
        )

    # Get sample rows
    import sqlite3
    from app.utils.database import get_db_path

    db_path = get_db_path(session_id)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 10')
        columns = [desc[0] for desc in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    return SampleDataResponse(
        table=table_name,
        columns=columns,
        rows=rows,
    )
