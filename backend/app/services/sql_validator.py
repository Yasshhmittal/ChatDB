"""
SQL Validator Service.
Multi-layer validation to ensure only safe queries are executed.

Layers:
1. Regex pre-check: block truly dangerous operations (EXEC, GRANT, ATTACH, etc.)
2. Multi-statement check: block queries with multiple statements (;)
3. AST parsing via sqlparse: verify statement type is an allowed type
4. Table whitelist: verify referenced tables exist (for SELECT queries)
"""

import re
import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where, Parenthesis
from sqlparse.tokens import Keyword, DML

from app.services.schema_extractor import get_table_names


class UnsafeQueryError(Exception):
    """Raised when a query fails safety validation."""
    pass


# Allowed SQL statement types
_ALLOWED_TYPES = {
    "SELECT", "INSERT", "UPDATE", "DELETE",
    "CREATE", "DROP", "ALTER", "TRUNCATE",
}

# Keywords that should NEVER appear in a user query (truly dangerous operations)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(EXEC|EXECUTE|GRANT|REVOKE|MERGE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)

# Patterns that indicate SQL injection attempts
_INJECTION_PATTERNS = re.compile(
    r"(--|/\*|\*/)",
    re.IGNORECASE,
)


def validate_sql(sql: str, session_id: str) -> str:
    """
    Validate a SQL query through multiple safety layers.

    Args:
        sql: The SQL query to validate
        session_id: The user's session (for table whitelist)

    Returns:
        Cleaned SQL string if safe

    Raises:
        UnsafeQueryError: If any validation layer fails
    """
    if not sql or not sql.strip():
        raise UnsafeQueryError("Empty query.")

    sql = sql.strip()

    # Remove trailing semicolons (common LLM output artifact)
    sql = sql.rstrip(";").strip()

    # ── Layer 1: Regex keyword check ──
    if _FORBIDDEN_KEYWORDS.search(sql):
        match = _FORBIDDEN_KEYWORDS.search(sql)
        raise UnsafeQueryError(
            f"Query contains forbidden keyword: {match.group().upper()}. "
            "This operation is not allowed."
        )

    # ── Layer 2: Injection pattern check ──
    if _INJECTION_PATTERNS.search(sql):
        raise UnsafeQueryError(
            "Query contains suspicious patterns that may indicate SQL injection."
        )

    # ── Layer 3: Multi-statement check ──
    # After stripping trailing semicolons, there should be no semicolons left
    if ";" in sql:
        raise UnsafeQueryError(
            "Multiple SQL statements detected. Only single queries are allowed."
        )

    # ── Layer 4: AST parsing — verify it's an allowed statement type ──
    try:
        parsed = sqlparse.parse(sql)
    except Exception as e:
        raise UnsafeQueryError(f"Failed to parse SQL: {e}")

    if len(parsed) != 1:
        raise UnsafeQueryError("Expected exactly one SQL statement.")

    stmt = parsed[0]
    stmt_type = stmt.get_type()

    # sqlparse may return None for DDL like TRUNCATE or CREATE — detect manually
    if stmt_type is None:
        first_token = sql.strip().split()[0].upper() if sql.strip() else ""
        if first_token in _ALLOWED_TYPES:
            stmt_type = first_token
        else:
            raise UnsafeQueryError(
                f"Unable to determine query type. First keyword: {first_token or 'UNKNOWN'}"
            )

    if stmt_type.upper() not in _ALLOWED_TYPES:
        raise UnsafeQueryError(
            f"Query type '{stmt_type}' is not allowed. "
            f"Allowed types: {', '.join(sorted(_ALLOWED_TYPES))}"
        )

    # ── Layer 5: Table whitelist check (for SELECT only) ──
    if stmt_type.upper() == "SELECT":
        try:
            valid_tables = set(get_table_names(session_id))
        except FileNotFoundError:
            raise UnsafeQueryError(f"No database found for session: {session_id}")

        if valid_tables:  # only check if we can get table names
            referenced = _extract_table_names(sql)
            # Filter out internal Postgres schemas
            invalid_tables = {
                t for t in referenced
                if t.lower() not in {v.lower() for v in valid_tables}
                and not t.lower().startswith("information_schema")
                and not t.lower().startswith("pg_")
                and not t.startswith("(")  # skip subqueries
            }
            if any("public." in t.lower() for t in referenced):
                raise UnsafeQueryError("Querying the public system schema is strictly prohibited.")
            if invalid_tables:
                raise UnsafeQueryError(
                    f"Query references tables that don't exist: {', '.join(invalid_tables)}. "
                    f"Available tables: {', '.join(valid_tables)}"
                )

    return sql


def get_query_type(sql: str) -> str:
    """
    Determine the type of a SQL statement.
    Returns the type string (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE).
    """
    sql = sql.strip().rstrip(";").strip()
    try:
        parsed = sqlparse.parse(sql)
        if parsed:
            stmt_type = parsed[0].get_type()
            if stmt_type:
                return stmt_type.upper()
    except Exception:
        pass

    # Fallback: use first keyword
    first_token = sql.split()[0].upper() if sql.strip() else "UNKNOWN"
    return first_token if first_token in _ALLOWED_TYPES else "UNKNOWN"


def _extract_table_names(sql: str) -> set[str]:
    """
    Extract table names referenced in a SQL query.
    Handles FROM, JOIN, and subquery contexts.
    """
    tables = set()

    # Use regex to find table names after FROM and JOIN
    # This is simpler and more reliable than walking the AST for this purpose
    patterns = [
        r'\bFROM\s+"?(\w+)"?',           # FROM table
        r'\bJOIN\s+"?(\w+)"?',            # JOIN table
        r'\bINTO\s+"?(\w+)"?',            # INTO table
    ]

    for pattern in patterns:
        matches = re.findall(pattern, sql, re.IGNORECASE)
        tables.update(matches)

    return tables
