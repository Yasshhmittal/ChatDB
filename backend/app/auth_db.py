import os
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import settings

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_timestamp() -> str:
    """Returns current IST timestamp in DD-MM-YYYY HH:MM:SS format."""
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

def init_db():
    """Initializes the authentication and application database using PostgreSQL."""
    settings.ensure_dirs()
    if not settings.DATABASE_URL:
        print("[WARN] DATABASE_URL not set! Waiting for it.")
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guest_sessions (
                session_id TEXT PRIMARY KEY,
                query_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()

@contextmanager
def get_db_connection():
    """Context manager for PostgreSQL connection."""
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

def get_user_by_username(username: str) -> dict | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()

def get_user_by_id(user_id: int) -> dict | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()

def create_user(name: str, username: str, password_hash: str) -> dict:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, username, password_hash, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, username, password_hash, get_ist_timestamp())
            )
            new_id = cursor.fetchone()['id']
            conn.commit()
            return get_user_by_id(new_id)
        except psycopg2.IntegrityError:
            conn.rollback()
            raise ValueError("Username already exists")

def get_guest_session(session_id: str) -> dict | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM guest_sessions WHERE session_id = %s", (session_id,))
        return cursor.fetchone()

def increment_guest_query(session_id: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO guest_sessions (session_id, query_count, created_at) VALUES (%s, 0, %s) ON CONFLICT (session_id) DO NOTHING",
            (session_id, get_ist_timestamp())
        )
        
        cursor.execute(
            "UPDATE guest_sessions SET query_count = query_count + 1 WHERE session_id = %s",
            (session_id,)
        )
        conn.commit()
        
        cursor.execute("SELECT query_count FROM guest_sessions WHERE session_id = %s", (session_id,))
        row = cursor.fetchone()
        return row['query_count'] if row else 0
