import sqlite3
import os
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from app.config import settings

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_timestamp() -> str:
    """Returns current IST timestamp in DD-MM-YYYY HH:MM:SS format."""
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")

APP_DB_PATH = os.path.join(settings.DATA_DIR, "app.db")

def init_db():
    """Initializes the authentication and application database."""
    # Ensure directory exists just in case
    settings.ensure_dirs()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Create guest_sessions table for rate limiting
        # query_count starts at 0, limit is 5
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
    """Context manager for SQLite database connection."""
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row  # Return dict-like row objects
    try:
        yield conn
    finally:
        conn.close()

# -------------------------------------------------------------
# User Database Operations
# -------------------------------------------------------------

def get_user_by_username(username: str) -> sqlite3.Row | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchone()

def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cursor.fetchone()

def create_user(name: str, username: str, password_hash: str) -> sqlite3.Row:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, username, password_hash, get_ist_timestamp())
            )
            conn.commit()
            return get_user_by_id(cursor.lastrowid)
        except sqlite3.IntegrityError:
            raise ValueError("Username already exists")

# -------------------------------------------------------------
# Guest Rate Limiting Operations
# -------------------------------------------------------------

def get_guest_session(session_id: str) -> sqlite3.Row | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM guest_sessions WHERE session_id = ?", (session_id,))
        return cursor.fetchone()

def increment_guest_query(session_id: str) -> int:
    """
    Increments the guest query count. Ensures row exists.
    Returns the updated count.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Initialize or ignore if exists
        cursor.execute(
            "INSERT OR IGNORE INTO guest_sessions (session_id, query_count, created_at) VALUES (?, 0, ?)",
            (session_id, get_ist_timestamp())
        )
        
        # Increment
        cursor.execute(
            "UPDATE guest_sessions SET query_count = query_count + 1 WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()
        
        # Fetch updated
        cursor.execute("SELECT query_count FROM guest_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return row['query_count'] if row else 0
