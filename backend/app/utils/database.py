"""
PostgreSQL connection manager.
Each user session gets its own isolated PostgreSQL SCHEMA.

Write operations (INSERT, UPDATE, DELETE, CREATE, DROP, etc.) from the chat
interface operate on a COPY (a cloned schema), so the user's uploaded
data is never modified.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Generator

from app.config import settings

def _sanitize(session_id: str) -> str:
    # Ensure safe schema names
    return str(session_id).replace('-', '_').lower()

def get_db_schema(session_id: str) -> str:
    """Get the ORIGINAL schema name for a session."""
    return f"s_{_sanitize(session_id)}"

def get_modified_db_schema(session_id: str) -> str:
    """Get the MODIFIED (copy) schema name for a session."""
    return f"s_{_sanitize(session_id)}_mod"

def schema_exists(conn, schema_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
        (schema_name,)
    )
    return cursor.fetchone() is not None

def has_modified_db(session_id: str) -> bool:
    """Check whether a modified copy already exists for this session."""
    with psycopg2.connect(settings.DATABASE_URL) as conn:
        return schema_exists(conn, get_modified_db_schema(session_id))

def db_exists(session_id: str) -> bool:
    """Check if a session's database schema exists."""
    with psycopg2.connect(settings.DATABASE_URL) as conn:
        return schema_exists(conn, get_db_schema(session_id))


@contextmanager
def get_write_connection(session_id: str) -> Generator:
    """
    Get a writable connection locked to the ORIGINAL schema.
    Used ONLY during file upload/import.
    """
    schema = get_db_schema(session_id)
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"SET search_path TO {schema}")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def clone_schema(conn, source: str, target: str):
    """Clones all tables from source schema to target schema in Postgres."""
    cur = conn.cursor()
    cur.execute(f"CREATE SCHEMA {target}")
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = %s
    """, (source,))
    tables = cur.fetchall()
    for row in tables:
        t = row['table_name']
        cur.execute(f'CREATE TABLE {target}."{t}" (LIKE {source}."{t}" INCLUDING ALL)')
        cur.execute(f'INSERT INTO {target}."{t}" SELECT * FROM {source}."{t}"')

@contextmanager
def get_readwrite_connection(session_id: str) -> Generator:
    """
    Get a read-write SQLite connection for DML/DDL operations from the chat.
    On first call, COPIES the original schema.
    """
    orig = get_db_schema(session_id)
    mod = get_modified_db_schema(session_id)
    
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        if not schema_exists(conn, orig):
            raise FileNotFoundError(f"No database found for session: {session_id}")
            
        if not schema_exists(conn, mod):
            clone_schema(conn, orig, mod)
            conn.commit()
            
        conn.cursor().execute(f"SET search_path TO {mod}")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_read_connection(session_id: str) -> Generator:
    """
    Get a READ-ONLY PostgreSQL connection locked to the ACTIVE schema.
    """
    orig = get_db_schema(session_id)
    mod = get_modified_db_schema(session_id)
    
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    # 1. Connection-level read-only protection in PostgreSQL
    conn.set_session(readonly=True)
    try:
        active = mod if schema_exists(conn, mod) else orig
        if not schema_exists(conn, active):
            raise FileNotFoundError(f"No database found for session: {session_id}")
            
        conn.cursor().execute(f"SET search_path TO {active}")
        yield conn
    finally:
        conn.close()
