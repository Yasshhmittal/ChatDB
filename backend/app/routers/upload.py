"""
Upload Router — File upload endpoints.
Accepts .csv and .sql files, creates per-user SQLite databases.
Supports single-file and multi-file uploads.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from typing import List

from app.config import settings
from app.models import UploadResponse, TableInfo, ColumnInfo
from app.services.file_processor import process_csv, process_sql, process_excel, process_json, generate_session_id
from app.services.rag_filter import build_embeddings
from app.routers.auth import get_current_user_or_none
from app.auth_db import log_upload, create_user_session, update_last_active

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".sql", ".xlsx", ".xls", ".json"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict | None = Depends(get_current_user_or_none),
):
    """
    Upload a CSV or SQL file to create a queryable database.

    - CSV files: auto-detect schema, create table, bulk insert
    - SQL files: execute CREATE TABLE + INSERT statements (safe only)

    Returns session_id (use this for all subsequent queries).
    """
    # ── Validate file ──
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()

    # Check file size
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max: {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    if not content:
        raise HTTPException(status_code=400, detail="File is empty.")

    # ── Process file ──
    try:
        if ext == ".csv":
            session_id, tables = await process_csv(content, file.filename)
        elif ext in {".xlsx", ".xls"}:
            session_id, tables = await process_excel(content, file.filename)
        elif ext == ".json":
            session_id, tables = await process_json(content, file.filename)
        else:
            session_id, tables = await process_sql(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file: {str(e)}",
        )

    # ── Build RAG embeddings for this session ──
    def safe_build_embeddings(sid: str):
        try:
            build_embeddings(sid)
        except Exception as e:
            print(f"[WARN] Failed to build RAG embeddings: {e}")

    background_tasks.add_task(safe_build_embeddings, session_id)

    # ── Build response ──
    table_infos = [
        TableInfo(
            name=t["name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count", 0),
        )
        for t in tables
    ]

    total_rows = sum(t.row_count for t in table_infos)

    # ── Log upload & create session link ──
    user_id = int(current_user["id"]) if current_user else None
    try:
        log_upload(
            session_id=session_id,
            file_name=file.filename,
            file_type=ext.lstrip("."),
            file_size_bytes=len(content),
            table_count=len(table_infos),
            total_rows=total_rows,
            user_id=user_id,
        )
        create_user_session(
            session_id=session_id,
            session_name=file.filename,
            user_id=user_id,
        )
        if user_id:
            update_last_active(user_id)
    except Exception as e:
        print(f"[WARN] Failed to log upload: {e}")

    return UploadResponse(
        session_id=session_id,
        tables=table_infos,
        message=f"Successfully imported {len(table_infos)} table(s) with {total_rows} total rows.",
    )


@router.post("/upload-multiple", response_model=UploadResponse)
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict | None = Depends(get_current_user_or_none),
):
    """
    Upload multiple CSV/SQL files into a single queryable database.

    All files are merged into one session so you can run cross-file queries
    (e.g. JOIN tables from different CSVs).

    Returns session_id covering all uploaded tables.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Generate a single session for all files
    session_id = generate_session_id()
    all_tables = []
    errors = []

    for file in files:
        if not file.filename:
            errors.append("Skipped a file with no filename.")
            continue

        ext = _get_extension(file.filename)
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"Skipped '{file.filename}': unsupported type ({ext}).")
            continue

        # Read file content
        content = await file.read()

        # Check file size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.MAX_UPLOAD_SIZE_MB:
            errors.append(f"Skipped '{file.filename}': too large ({size_mb:.1f} MB).")
            continue

        if not content:
            errors.append(f"Skipped '{file.filename}': file is empty.")
            continue

        # Process file into the shared session
        try:
            if ext == ".csv":
                _, tables = await process_csv(content, file.filename, session_id=session_id)
            elif ext in {".xlsx", ".xls"}:
                _, tables = await process_excel(content, file.filename, session_id=session_id)
            elif ext == ".json":
                _, tables = await process_json(content, file.filename, session_id=session_id)
            else:
                _, tables = await process_sql(content, file.filename, session_id=session_id)
            all_tables.extend(tables)
        except ValueError as e:
            errors.append(f"Skipped '{file.filename}': {str(e)}")
        except Exception as e:
            errors.append(f"Failed '{file.filename}': {str(e)}")

    if not all_tables:
        error_detail = "No files were successfully processed."
        if errors:
            error_detail += " Errors: " + "; ".join(errors)
        raise HTTPException(status_code=400, detail=error_detail)

    # ── Build RAG embeddings for combined session ──
    def safe_build_embeddings(sid: str):
        try:
            build_embeddings(sid)
        except Exception as e:
            print(f"[WARN] Failed to build RAG embeddings: {e}")

    background_tasks.add_task(safe_build_embeddings, session_id)

    # ── Build response ──
    table_infos = [
        TableInfo(
            name=t["name"],
            columns=[ColumnInfo(**c) for c in t["columns"]],
            row_count=t.get("row_count", 0),
        )
        for t in all_tables
    ]

    total_rows = sum(t.row_count for t in table_infos)
    file_count = len(files) - len(errors)

    # ── Log uploads & create session link ──
    user_id = int(current_user["id"]) if current_user else None
    try:
        for f in files:
            if f.filename:
                f_ext = _get_extension(f.filename).lstrip(".")
                log_upload(
                    session_id=session_id,
                    file_name=f.filename,
                    file_type=f_ext,
                    file_size_bytes=0,
                    table_count=0,
                    total_rows=0,
                    user_id=user_id,
                )
        create_user_session(
            session_id=session_id,
            session_name=f"{file_count} files",
            user_id=user_id,
        )
        if user_id:
            update_last_active(user_id)
    except Exception as e:
        print(f"[WARN] Failed to log multi-upload: {e}")

    # Build message
    msg = f"Successfully imported {len(table_infos)} table(s) from {file_count} file(s) with {total_rows} total rows."
    if errors:
        msg += f" ({len(errors)} file(s) skipped)"

    return UploadResponse(
        session_id=session_id,
        tables=table_infos,
        message=msg,
    )


def _get_extension(filename: str) -> str:
    """Get lowercase file extension."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[1].lower()
    return ""
