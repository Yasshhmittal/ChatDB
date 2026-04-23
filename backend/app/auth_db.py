import os
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from typing import Optional
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
        
        # ── Core: users table ──
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ── Add new columns to users (idempotent) ──
        for col_def in [
            "total_queries INTEGER DEFAULT 0",
            "total_uploads INTEGER DEFAULT 0",
            "last_active_at TEXT",
            "is_active BOOLEAN DEFAULT TRUE",
        ]:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except psycopg2.errors.DuplicateColumn:
                conn.rollback()
        
        # ── Core: guest_sessions table ──
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guest_sessions (
                session_id TEXT PRIMARY KEY,
                query_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ── New: query_history table ──
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                generated_sql TEXT,
                query_type TEXT DEFAULT 'SELECT',
                row_count INTEGER DEFAULT 0,
                execution_time_ms INTEGER,
                retries_used INTEGER DEFAULT 0,
                was_successful BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ── New: uploaded_files table ──
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                session_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size_bytes INTEGER,
                table_count INTEGER DEFAULT 0,
                total_rows INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ── New: user_sessions table ──
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                session_id TEXT NOT NULL,
                session_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_accessed_at TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        
        # ── Indexes for performance ──
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_query_history_user ON query_history(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_query_history_session ON query_history(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_query_history_created ON query_history(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_uploaded_files_user ON uploaded_files(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_uploaded_files_session ON uploaded_files(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_session ON user_sessions(session_id)",
        ]
        for stmt in index_statements:
            cursor.execute(stmt)
        
        conn.commit()
        print("[OK] Database schema initialized (all tables ready)")

@contextmanager
def get_db_connection():
    """Context manager for PostgreSQL connection."""
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


# ═══════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════

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
                "INSERT INTO users (name, username, password_hash, created_at, last_active_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, username, password_hash, get_ist_timestamp(), get_ist_timestamp())
            )
            new_id = cursor.fetchone()['id']
            conn.commit()
            return get_user_by_id(new_id)
        except psycopg2.IntegrityError:
            conn.rollback()
            raise ValueError("Username already exists")


# ═══════════════════════════════════════════════
# Guest Sessions
# ═══════════════════════════════════════════════

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


# ═══════════════════════════════════════════════
# Query History
# ═══════════════════════════════════════════════

def log_query(
    session_id: str,
    question: str,
    generated_sql: str = "",
    query_type: str = "SELECT",
    row_count: int = 0,
    execution_time_ms: int = 0,
    retries_used: int = 0,
    was_successful: bool = True,
    error_message: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    """Log a query to query_history and increment the user's total_queries counter."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO query_history 
               (user_id, session_id, question, generated_sql, query_type, 
                row_count, execution_time_ms, retries_used, was_successful, error_message, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, session_id, question, generated_sql, query_type,
             row_count, execution_time_ms, retries_used, was_successful, error_message,
             get_ist_timestamp())
        )
        # Increment user's lifetime query counter
        if user_id:
            cursor.execute(
                "UPDATE users SET total_queries = total_queries + 1 WHERE id = %s",
                (user_id,)
            )
        conn.commit()


def get_user_query_history(user_id: int, page: int = 1, limit: int = 20) -> dict:
    """Fetch paginated query history for a user."""
    offset = (page - 1) * limit
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM query_history WHERE user_id = %s", (user_id,))
        total = cursor.fetchone()['total']
        # Paginated results
        cursor.execute(
            """SELECT id, session_id, question, generated_sql, query_type, row_count,
                      execution_time_ms, retries_used, was_successful, error_message, created_at
               FROM query_history WHERE user_id = %s
               ORDER BY id DESC LIMIT %s OFFSET %s""",
            (user_id, limit, offset)
        )
        queries = cursor.fetchall()
        return {
            "queries": [dict(q) for q in queries],
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1,
        }


# ═══════════════════════════════════════════════
# Uploaded Files
# ═══════════════════════════════════════════════

def log_upload(
    session_id: str,
    file_name: str,
    file_type: str,
    file_size_bytes: int = 0,
    table_count: int = 0,
    total_rows: int = 0,
    user_id: Optional[int] = None,
) -> None:
    """Log a file upload and increment the user's total_uploads counter."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO uploaded_files 
               (user_id, session_id, file_name, file_type, file_size_bytes, table_count, total_rows, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, session_id, file_name, file_type, file_size_bytes,
             table_count, total_rows, get_ist_timestamp())
        )
        # Increment user's lifetime upload counter
        if user_id:
            cursor.execute(
                "UPDATE users SET total_uploads = total_uploads + 1 WHERE id = %s",
                (user_id,)
            )
        conn.commit()


def get_user_uploads(user_id: int) -> list[dict]:
    """Fetch all upload records for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, session_id, file_name, file_type, file_size_bytes,
                      table_count, total_rows, created_at
               FROM uploaded_files WHERE user_id = %s
               ORDER BY id DESC""",
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════
# User Sessions
# ═══════════════════════════════════════════════

def create_user_session(
    session_id: str,
    session_name: str = "",
    user_id: Optional[int] = None,
) -> None:
    """Record a user ↔ session link."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_sessions (user_id, session_id, session_name, last_accessed_at, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, session_id, session_name or "Untitled Session",
             get_ist_timestamp(), get_ist_timestamp())
        )
        conn.commit()


def touch_user_session(session_id: str) -> None:
    """Update last_accessed_at for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_sessions SET last_accessed_at = %s WHERE session_id = %s",
            (get_ist_timestamp(), session_id)
        )
        conn.commit()


def get_user_sessions(user_id: int) -> list[dict]:
    """Fetch all sessions for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, session_id, session_name, is_active, last_accessed_at, created_at
               FROM user_sessions WHERE user_id = %s AND is_active = TRUE
               ORDER BY id DESC""",
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════
# User Activity / Stats
# ═══════════════════════════════════════════════

def update_last_active(user_id: int) -> None:
    """Touch the user's last_active_at timestamp."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_active_at = %s WHERE id = %s",
            (get_ist_timestamp(), user_id)
        )
        conn.commit()


def get_user_stats(user_id: int) -> dict:
    """Get aggregated statistics for a user's dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Basic user info
        cursor.execute(
            "SELECT total_queries, total_uploads, last_active_at, created_at FROM users WHERE id = %s",
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            return {}
        
        # Success rate
        cursor.execute(
            """SELECT 
                 COUNT(*) as total,
                 SUM(CASE WHEN was_successful THEN 1 ELSE 0 END) as successful
               FROM query_history WHERE user_id = %s""",
            (user_id,)
        )
        rate_row = cursor.fetchone()
        total_q = rate_row['total'] or 0
        success_q = rate_row['successful'] or 0
        
        # Most used query types
        cursor.execute(
            """SELECT query_type, COUNT(*) as count
               FROM query_history WHERE user_id = %s
               GROUP BY query_type ORDER BY count DESC LIMIT 5""",
            (user_id,)
        )
        query_types = [dict(r) for r in cursor.fetchall()]
        
        # Average execution time
        cursor.execute(
            "SELECT AVG(execution_time_ms) as avg_time FROM query_history WHERE user_id = %s AND was_successful = TRUE",
            (user_id,)
        )
        avg_row = cursor.fetchone()
        avg_time = round(avg_row['avg_time'] or 0, 1)
        
        # Active sessions count
        cursor.execute(
            "SELECT COUNT(*) as count FROM user_sessions WHERE user_id = %s AND is_active = TRUE",
            (user_id,)
        )
        sessions_count = cursor.fetchone()['count']
        
        # Recent queries (last 5)
        cursor.execute(
            """SELECT question, generated_sql, query_type, was_successful, created_at
               FROM query_history WHERE user_id = %s
               ORDER BY id DESC LIMIT 5""",
            (user_id,)
        )
        recent_queries = [dict(r) for r in cursor.fetchall()]
        
        return {
            "total_queries": user_row['total_queries'] or 0,
            "total_uploads": user_row['total_uploads'] or 0,
            "last_active_at": user_row['last_active_at'],
            "member_since": user_row['created_at'],
            "success_rate": round((success_q / total_q * 100), 1) if total_q > 0 else 100.0,
            "avg_execution_time_ms": avg_time,
            "query_type_breakdown": query_types,
            "active_sessions": sessions_count,
            "recent_queries": recent_queries,
        }
