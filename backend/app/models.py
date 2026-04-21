"""
Pydantic models for all API request/response shapes.
Single source of truth for data contracts.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────

class ColumnInfo(BaseModel):
    """Single column metadata."""
    name: str
    dtype: str  # e.g. "INTEGER", "TEXT", "REAL"


class TableInfo(BaseModel):
    """Single table metadata."""
    name: str
    columns: list[ColumnInfo]
    row_count: int = 0


class UploadResponse(BaseModel):
    """Response after successful file upload."""
    session_id: str
    tables: list[TableInfo]
    message: str


# ──────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────

class SchemaResponse(BaseModel):
    """Full schema info for a session's database."""
    session_id: str
    tables: list[TableInfo]


class SampleDataResponse(BaseModel):
    """Sample rows from a table."""
    table: str
    columns: list[str]
    rows: list[list[Any]]


# ──────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in chat history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Incoming chat request from frontend."""
    session_id: str
    question: str
    chat_history: list[ChatMessage] = Field(default_factory=list)


class ChartConfig(BaseModel):
    """Chart rendering configuration (rule-based, no LLM)."""
    chart_type: str  # "bar", "line", "pie", "scatter", or "none"
    labels: list[str] = Field(default_factory=list)
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    x_label: str = ""
    y_label: str = ""


class ChatResponse(BaseModel):
    """Full response to a chat question."""
    question: str
    sql_query: str = ""
    results: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    explanation: str = ""
    chart: Optional[ChartConfig] = None
    error: Optional[str] = None
    retries_used: int = 0
    query_type: str = "SELECT"
    affected_rows: int = 0


# ──────────────────────────────────────────────
# Errors
# ──────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
