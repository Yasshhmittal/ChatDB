"""
Download Router — Let users download original or modified database files
as SQLite (.db) or comma-separated values (.csv).
"""

import io
import zipfile
import sqlite3
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.utils.database import db_exists, has_modified_db, get_db_schema, get_modified_db_schema
from app.config import settings

router = APIRouter()


@router.get("/download/{session_id}/original")
async def download_original(session_id: str):
    raise HTTPException(
        status_code=501, 
        detail="SQLite (.db) downloads are disabled in the Cloud PostgreSQL architecture. Please use the CSV download option instead."
    )


@router.get("/download/{session_id}/modified")
async def download_modified(session_id: str):
    raise HTTPException(
        status_code=501, 
        detail="SQLite (.db) downloads are disabled in the Cloud PostgreSQL architecture. Please use the CSV download option instead."
    )


@router.get("/download/{session_id}/csv/{db_type}")
async def download_csv(session_id: str, db_type: str):
    """
    Download the database as CSV.
    db_type can be "original" or "modified".
    If there is 1 table, returns a .csv file.
    If there are multiple tables, returns a .zip containing .csv files.
    """
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    if db_type == "modified":
        if not has_modified_db(session_id):
            raise HTTPException(
                status_code=404,
                detail="No modified database found.",
            )
        db_schema = get_modified_db_schema(session_id)
        filename_prefix = f"{session_id}_modified"
    elif db_type == "original":
        db_schema = get_db_schema(session_id)
        filename_prefix = f"{session_id}_original"
    else:
        raise HTTPException(status_code=400, detail="Invalid db_type. Must be 'original' or 'modified'.")

    # Connect to DB and get tables
    import psycopg2
    from psycopg2.extras import RealDictCursor
    with psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (db_schema,))
        tables = [row["table_name"] for row in cursor.fetchall()]

        if not tables:
            raise HTTPException(status_code=404, detail="No tables found in database.")

        if len(tables) == 1:
            table_name = tables[0]
            # Set schema path explicitly
            cursor.execute(f"SET search_path TO {db_schema}")
            cursor.execute(f'SELECT * FROM "{table_name}"')
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame([dict(r) for r in cursor.fetchall()], columns=columns)
            
            stream = io.StringIO()
            df.to_csv(stream, index=False)
            response = iter([stream.getvalue()])
            
            return StreamingResponse(
                response,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{table_name}_{filename_prefix}.csv"'}
            )
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                cursor.execute(f"SET search_path TO {db_schema}")
                for table_name in tables:
                    cursor.execute(f'SELECT * FROM "{table_name}"')
                    columns = [desc[0] for desc in cursor.description]
                    df = pd.DataFrame([dict(r) for r in cursor.fetchall()], columns=columns)
                    csv_string = df.to_csv(index=False)
                    zip_file.writestr(f"{table_name}.csv", csv_string.encode("utf-8"))
            
            zip_buffer.seek(0)
            return StreamingResponse(
                iter([zip_buffer.getvalue()]),
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.zip"'}
            )


@router.get("/download/{session_id}/status")
async def download_status(session_id: str):
    """Check whether original and/or modified databases are available for download."""
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    return {
        "session_id": session_id,
        "original_available": True,
        "modified_available": has_modified_db(session_id),
    }
