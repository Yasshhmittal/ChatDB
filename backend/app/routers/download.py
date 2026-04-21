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

from app.utils.database import get_db_path, get_modified_db_path, db_exists, has_modified_db

router = APIRouter()


@router.get("/download/{session_id}/original")
async def download_original(session_id: str):
    """Download the original (unmodified) database file as .db."""
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    db_path = get_db_path(session_id)
    return FileResponse(
        path=str(db_path),
        filename=f"{session_id}_original.db",
        media_type="application/x-sqlite3",
    )


@router.get("/download/{session_id}/modified")
async def download_modified(session_id: str):
    """Download the modified (copy) database file as .db."""
    if not db_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    if not has_modified_db(session_id):
        raise HTTPException(
            status_code=404,
            detail="No modified database found. Run a write query first (INSERT, UPDATE, DELETE, etc.).",
        )

    db_path = get_modified_db_path(session_id)
    return FileResponse(
        path=str(db_path),
        filename=f"{session_id}_modified.db",
        media_type="application/x-sqlite3",
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
        db_path = get_modified_db_path(session_id)
        filename_prefix = f"{session_id}_modified"
    elif db_type == "original":
        db_path = get_db_path(session_id)
        filename_prefix = f"{session_id}_original"
    else:
        raise HTTPException(status_code=400, detail="Invalid db_type. Must be 'original' or 'modified'.")

    # Connect to DB and get tables
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            raise HTTPException(status_code=404, detail="No tables found in database.")

        if len(tables) == 1:
            # Single table -> Return just one CSV
            table_name = tables[0]
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
            
            # Write to BytesIO
            stream = io.StringIO()
            df.to_csv(stream, index=False)
            response = iter([stream.getvalue()])
            
            return StreamingResponse(
                response,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{table_name}_{filename_prefix}.csv"'}
            )
        else:
            # Multiple tables -> Return a ZIP file of CSVs
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for table_name in tables:
                    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
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
