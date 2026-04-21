"""
SQLite connection manager.
Each user session gets its own isolated .db file.

Write operations (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) from the chat
interface operate on a COPY of the original database, so the user's uploaded
data is never modified.  Users can download both the original and the modified
version.
"""

import shutil
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from app.config import settings


def get_db_path(session_id: str) -> Path:
    """Get the ORIGINAL SQLite database file path for a session."""
    return Path(settings.DATA_DIR) / f"{session_id}.db"


def get_modified_db_path(session_id: str) -> Path:
    """Get the MODIFIED (copy) database file path for a session."""
    return Path(settings.DATA_DIR) / f"{session_id}_modified.db"


def has_modified_db(session_id: str) -> bool:
    """Check whether a modified copy already exists for this session."""
    return get_modified_db_path(session_id).exists()


def get_active_db_path(session_id: str) -> Path:
    """
    Return whichever database the user should query against.
    If a modified copy exists (i.e. the user has run write queries),
    subsequent SELECTs should see those changes.
    Otherwise fall back to the original.
    """
    modified = get_modified_db_path(session_id)
    if modified.exists():
        return modified
    return get_db_path(session_id)


def db_exists(session_id: str) -> bool:
    """Check if a session's database exists."""
    return get_db_path(session_id).exists()


@contextmanager
def get_write_connection(session_id: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Get a writable SQLite connection.
    Used ONLY during file upload/import.
    """
    db_path = get_db_path(session_id)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent performance
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_read_connection(session_id: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Get a READ-ONLY SQLite connection.
    Points to the *active* database (modified copy if it exists, else original)
    so that SELECT queries after a write reflect the changes.

    Three layers of read-only protection:
    1. URI mode=ro: connection-level read-only
    2. PRAGMA query_only=ON: statement-level read-only
    3. SQL validator filters out write statements before we get here
    """
    db_path = get_active_db_path(session_id)
    if not db_path.exists():
        raise FileNotFoundError(f"No database found for session: {session_id}")

    # file: URI with mode=ro makes the connection truly read-only
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=settings.QUERY_TIMEOUT_SECONDS)
    conn.execute("PRAGMA query_only=ON")  # extra safety layer
    conn.row_factory = sqlite3.Row  # return dict-like rows
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_readwrite_connection(session_id: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Get a read-write SQLite connection for DML/DDL operations from the chat.

    On first call, COPIES the original database so the original is never
    touched.  All subsequent writes go to the same copy.
    """
    original = get_db_path(session_id)
    if not original.exists():
        raise FileNotFoundError(f"No database found for session: {session_id}")

    modified = get_modified_db_path(session_id)
    if not modified.exists():
        shutil.copy2(str(original), str(modified))

    conn = sqlite3.connect(str(modified), timeout=settings.QUERY_TIMEOUT_SECONDS)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
