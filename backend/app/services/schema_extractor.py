"""
Schema Extractor Service.
Extracts full database schema metadata for LLM prompting.
Formats schema as structured text that LLMs understand well.
"""

import sqlite3
from app.utils.database import get_db_path


def extract_schema(session_id: str) -> list[dict]:
    """
    Extract complete schema from a session's database.

    Returns list of table dicts with:
    - name: table name
    - columns: list of {name, dtype}
    - row_count: number of rows
    - sample_rows: first 3 rows as list of dicts
    """
    db_path = get_db_path(session_id)
    if not db_path.exists():
        raise FileNotFoundError(f"No database for session: {session_id}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Get all user tables
        tables_cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row["name"] for row in tables_cursor.fetchall()]

        schema = []
        for table_name in table_names:
            # Column info
            col_cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
            columns = [
                {"name": row["name"], "dtype": row["type"] or "TEXT"}
                for row in col_cursor.fetchall()
            ]

            # Row count
            count = conn.execute(
                f'SELECT COUNT(*) as cnt FROM "{table_name}"'
            ).fetchone()["cnt"]

            # Sample rows (3 rows for LLM context)
            sample_cursor = conn.execute(
                f'SELECT * FROM "{table_name}" LIMIT 3'
            )
            sample_cols = [desc[0] for desc in sample_cursor.description]
            sample_rows = [dict(zip(sample_cols, row)) for row in sample_cursor.fetchall()]

            schema.append({
                "name": table_name,
                "columns": columns,
                "row_count": count,
                "sample_rows": sample_rows,
            })

        return schema
    finally:
        conn.close()


def format_schema_for_llm(tables: list[dict], include_samples: bool = True) -> str:
    """
    Format schema as structured text for LLM prompt injection.

    Example output:
    TABLE: customers (1500 rows)
    COLUMNS: id (INTEGER), name (TEXT), email (TEXT), created_at (TEXT)
    SAMPLE DATA:
    | id | name | email | created_at |
    | 1 | John | john@email.com | 2024-01-15 |
    """
    parts = []

    for table in tables:
        col_str = ", ".join(
            f"{c['name']} ({c['dtype']})" for c in table["columns"]
        )
        section = f"TABLE: {table['name']} ({table['row_count']} rows)\n"
        section += f"COLUMNS: {col_str}\n"

        if include_samples and table.get("sample_rows"):
            cols = [c["name"] for c in table["columns"]]
            section += "SAMPLE DATA:\n"
            section += "| " + " | ".join(cols) + " |\n"
            for row in table["sample_rows"]:
                vals = [str(row.get(c, "")) for c in cols]
                section += "| " + " | ".join(vals) + " |\n"

        parts.append(section)

    return "\n".join(parts)


def get_table_names(session_id: str) -> list[str]:
    """Get just the table names for a session."""
    db_path = get_db_path(session_id)
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_table_descriptions(session_id: str) -> dict[str, str]:
    """
    Get table descriptions for RAG embedding.
    Format: "table_name: col1 (type), col2 (type), ..."
    Returns dict of {table_name: description_string}
    """
    schema = extract_schema(session_id)
    descriptions = {}
    for table in schema:
        col_str = ", ".join(
            f"{c['name']} ({c['dtype']})" for c in table["columns"]
        )
        descriptions[table["name"]] = f"{table['name']}: {col_str}"
    return descriptions
