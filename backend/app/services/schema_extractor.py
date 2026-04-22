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
    from app.utils.database import get_read_connection
    from psycopg2.extras import RealDictCursor

    with get_read_connection(session_id) as conn:
        tables_cursor = conn.cursor()
        tables_cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
        table_names = [row["table_name"] for row in tables_cursor.fetchall()]

        schema = []
        for table_name in table_names:
            col_cursor = conn.cursor()
            col_cursor.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = %s",
                (table_name,)
            )
            columns = [
                {"name": row["column_name"], "dtype": row["data_type"]}
                for row in col_cursor.fetchall()
            ]

            count_cur = conn.cursor()
            count_cur.execute(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
            count = count_cur.fetchone()["cnt"]

            sample_cursor = conn.cursor()
            sample_cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
            sample_cols = [desc[0] for desc in sample_cursor.description]
            sample_rows = [dict(zip(sample_cols, row.values())) if isinstance(row, dict) else dict(row) for row in sample_cursor.fetchall()]

            schema.append({
                "name": table_name,
                "columns": columns,
                "row_count": count,
                "sample_rows": sample_rows,
            })

        return schema


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
    from app.utils.database import get_read_connection
    with get_read_connection(session_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
        return [row["table_name"] for row in cursor.fetchall()]


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
