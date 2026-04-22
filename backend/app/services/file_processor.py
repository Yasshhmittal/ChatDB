"""
File Processor Service.
Handles CSV and SQL file uploads → creates SQLite databases.

CSV: Auto-detects column types, creates table, bulk inserts via pandas.
SQL: Filters dangerous statements, executes only CREATE TABLE + INSERT.
"""

import re
import uuid
from pathlib import Path

import pandas as pd
import psycopg2
import sqlalchemy

from app.config import settings
from app.utils.database import get_write_connection, get_db_schema


# SQL statements we allow from uploaded .sql files
_ALLOWED_SQL_PATTERNS = re.compile(
    r"^\s*(CREATE\s+TABLE|INSERT\s+INTO)",
    re.IGNORECASE,
)

# Dangerous keywords to block in uploaded SQL
_BLOCKED_SQL_PATTERNS = re.compile(
    r"\b(DROP|DELETE|UPDATE|ALTER|TRUNCATE|EXEC|GRANT|REVOKE|MERGE)\b",
    re.IGNORECASE,
)


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return uuid.uuid4().hex[:16]


def sanitize_table_name(name: str) -> str:
    """
    Make a string safe for use as a SQLite table name.
    Removes special chars, replaces spaces with underscores.
    """
    # Remove file extension if present
    name = Path(name).stem
    # Replace non-alphanumeric with underscore
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    # Remove leading digits
    name = re.sub(r"^[0-9]+", "", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "imported_data"


def sanitize_column_name(name: str) -> str:
    """Make a string safe for use as a SQLite column name."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", str(name))
    name = re.sub(r"^[0-9]+", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name.lower() or "column"


def _process_dataframe(df: pd.DataFrame, filename: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """
    Process a pandas DataFrame:
    1. Sanitize column names
    2. Create SQLite table with inferred types
    3. Bulk insert all rows
    """
    session_id = session_id or generate_session_id()
    table_name = sanitize_table_name(filename)

    if df.empty:
        raise ValueError("File is empty or has no valid data.")

    # Sanitize column names (prevent SQL injection via column names)
    original_cols = df.columns.tolist()
    sanitized_cols = []
    seen = set()
    for col in original_cols:
        clean = sanitize_column_name(col)
        # Handle duplicates
        if clean in seen:
            i = 2
            while f"{clean}_{i}" in seen:
                i += 1
            clean = f"{clean}_{i}"
        seen.add(clean)
        sanitized_cols.append(clean)

    df.columns = sanitized_cols

    # Convert complex objects like lists/dicts into strings so SQLite can store them
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
            import json
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)

    # Convert db URL
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    engine = sqlalchemy.create_engine(db_url)
    schema = get_db_schema(session_id)

    # Force create schema
    with get_write_connection(session_id):
        pass 

    # Write to Postgres
    with engine.begin() as sql_conn:
        df.to_sql(table_name, sql_conn, schema=schema, if_exists="replace", index=False, chunksize=500, method="multi")

    # Build table info
    tables = [_get_table_info(session_id, table_name)]
    return session_id, tables


async def process_csv(file_content: bytes, filename: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """Process a CSV file."""
    import io
    import asyncio

    def _sync_process():
        # Read CSV — handle common encodings
        try:
            df = pd.read_csv(io.BytesIO(file_content), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(file_content), encoding="latin-1")
        return _process_dataframe(df, filename, session_id)

    return await asyncio.to_thread(_sync_process)


async def process_excel(file_content: bytes, filename: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """Process an Excel file."""
    import io
    import asyncio

    def _sync_process():
        try:
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {e}")
        return _process_dataframe(df, filename, session_id)

    return await asyncio.to_thread(_sync_process)


async def process_json(file_content: bytes, filename: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """Process a JSON file."""
    import io
    import asyncio

    def _sync_process():
        try:
            df = pd.read_json(io.BytesIO(file_content))
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {e}")
        return _process_dataframe(df, filename, session_id)

    return await asyncio.to_thread(_sync_process)


async def process_sql(file_content: bytes, filename: str, session_id: str | None = None) -> tuple[str, list[dict]]:
    """
    Process a SQL file:
    1. Parse SQL statements
    2. Filter: only allow CREATE TABLE and INSERT
    3. Block any dangerous operations
    4. Execute safe statements into SQLite

    If session_id is provided, adds to existing database.
    Returns: (session_id, list of table info dicts)
    """
    session_id = session_id or generate_session_id()

    # Decode SQL content
    try:
        sql_text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        sql_text = file_content.decode("latin-1")

    # Split into individual statements
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    if not statements:
        raise ValueError("SQL file contains no valid statements.")

    safe_statements = []
    for stmt in statements:
        # Block dangerous operations
        if _BLOCKED_SQL_PATTERNS.search(stmt):
            continue  # silently skip dangerous statements

        # Only allow CREATE TABLE and INSERT
        if _ALLOWED_SQL_PATTERNS.match(stmt):
            # Convert MySQL-specific syntax to SQLite-compatible
            stmt = _mysql_to_sqlite(stmt)
            safe_statements.append(stmt)

    if not safe_statements:
        raise ValueError(
            "SQL file contains no safe CREATE TABLE or INSERT statements."
        )

    import asyncio

    def _sync_execute():
        # Execute safe statements
        with get_write_connection(session_id) as conn:
            with conn.cursor() as cur:
                for stmt in safe_statements:
                    try:
                        cur.execute(stmt)
                    except psycopg2.Error as e:
                        # Log but don't fail entire upload for one bad statement
                        print(f"[WARN] Skipping statement due to error: {e}")
                        continue
            conn.commit()

        # Get all created tables
        tables = _get_all_tables_info(session_id)

        if not tables:
            raise ValueError("No tables were created from the SQL file.")

        return session_id, tables

    return await asyncio.to_thread(_sync_execute)


def _mysql_to_sqlite(sql: str) -> str:
    """
    Convert common MySQL syntax to SQLite-compatible SQL.
    Handles AUTO_INCREMENT, ENGINE, CHARSET, backticks, etc.
    """
    # Remove MySQL-specific clauses
    sql = re.sub(r"\s+AUTO_INCREMENT\s*=?\s*\d*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+ENGINE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+DEFAULT\s+CHARSET\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+COLLATE\s*=?\s*\w+", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+CHARACTER\s+SET\s+\w+", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+COMMENT\s+'[^']*'", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+UNSIGNED", "", sql, flags=re.IGNORECASE)

    # Replace backticks with double quotes (SQLite standard)
    sql = sql.replace("`", '"')

    # AUTO_INCREMENT → AUTOINCREMENT (SQLite)
    sql = re.sub(r"AUTO_INCREMENT", "AUTOINCREMENT", sql, flags=re.IGNORECASE)

    # MySQL INT types → INTEGER
    sql = re.sub(r"\bINT\(\d+\)", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bBIGINT\b", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bSMALLINT\b", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bTINYINT\b", "INTEGER", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bMEDIUMINT\b", "INTEGER", sql, flags=re.IGNORECASE)

    # VARCHAR(n) → TEXT
    sql = re.sub(r"\bVARCHAR\(\d+\)", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bLONGTEXT\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bMEDIUMTEXT\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bTINYTEXT\b", "TEXT", sql, flags=re.IGNORECASE)

    # DOUBLE/FLOAT → REAL
    sql = re.sub(r"\bDOUBLE\b", "REAL", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bFLOAT\b", "REAL", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)", "REAL", sql, flags=re.IGNORECASE)

    # DATETIME/TIMESTAMP → TEXT (SQLite stores dates as text)
    sql = re.sub(r"\bDATETIME\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bTIMESTAMP\b", "TEXT", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bDATE\b", "TEXT", sql, flags=re.IGNORECASE)

    # Remove IF NOT EXISTS for broader compatibility
    # (SQLite supports it, but some edge cases fail)

    return sql


def _get_table_info(session_id: str, table_name: str) -> dict:
    """Get column info and row count for a single table."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        schema = get_db_schema(session_id)
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
            (schema, table_name)
        )
        columns = [{"name": row["column_name"], "dtype": row["data_type"]} for row in cur.fetchall()]
        
        cur.execute(f'SELECT COUNT(*) FROM {schema}."{table_name}"')
        row_count = cur.fetchone()['count']
        return {
            "name": table_name,
            "columns": columns,
            "row_count": row_count,
        }
    finally:
        conn.close()

def _get_all_tables_info(session_id: str) -> list[dict]:
    """Get info for all tables in a session's database."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        schema = get_db_schema(session_id)
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (schema,)
        )
        table_names = [row["table_name"] for row in cur.fetchall()]
    finally:
        conn.close()

    return [_get_table_info(session_id, name) for name in table_names]
