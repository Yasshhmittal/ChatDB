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


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

class QueryHistoryItem(BaseModel):
    """A single item in query history."""
    id: int
    session_id: str
    question: str
    generated_sql: Optional[str] = None
    query_type: str = "SELECT"
    row_count: int = 0
    execution_time_ms: Optional[int] = None
    retries_used: int = 0
    was_successful: bool = True
    error_message: Optional[str] = None
    created_at: str


class QueryHistoryResponse(BaseModel):
    """Paginated query history response."""
    queries: list[QueryHistoryItem]
    total: int
    page: int
    limit: int
    total_pages: int


class UploadHistoryItem(BaseModel):
    """A single uploaded file record."""
    id: int
    session_id: str
    file_name: str
    file_type: str
    file_size_bytes: Optional[int] = None
    table_count: int = 0
    total_rows: int = 0
    created_at: str


class UserSessionItem(BaseModel):
    """A user's data session."""
    id: int
    session_id: str
    session_name: Optional[str] = None
    is_active: bool = True
    last_accessed_at: Optional[str] = None
    created_at: str


class QueryTypeBreakdown(BaseModel):
    """Query type count."""
    query_type: str
    count: int


class RecentQuery(BaseModel):
    """Minimal query info for dashboard."""
    question: str
    generated_sql: Optional[str] = None
    query_type: str
    was_successful: bool
    created_at: str


class UserStatsResponse(BaseModel):
    """Aggregated user statistics for analytics dashboard."""
    total_queries: int = 0
    total_uploads: int = 0
    last_active_at: Optional[str] = None
    member_since: Optional[str] = None
    success_rate: float = 100.0
    avg_execution_time_ms: float = 0.0
    query_type_breakdown: list[QueryTypeBreakdown] = Field(default_factory=list)
    active_sessions: int = 0
    recent_queries: list[RecentQuery] = Field(default_factory=list)

