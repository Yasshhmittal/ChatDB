"""
Analytics Router — User statistics, query history, and upload history.
Requires authentication (JWT token).
"""

from fastapi import APIRouter, HTTPException, Depends, Query

from app.models import (
    QueryHistoryResponse,
    UploadHistoryItem,
    UserSessionItem,
    UserStatsResponse,
)
from app.routers.auth import get_current_user_or_none
from app.auth_db import get_user_query_history, get_user_uploads, get_user_sessions, get_user_stats


router = APIRouter()


def _require_auth(current_user: dict | None = Depends(get_current_user_or_none)):
    """Dependency that enforces authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    return current_user


# ──────────────────────────────────────────────
# Dashboard Stats
# ──────────────────────────────────────────────

@router.get("/stats", response_model=UserStatsResponse)
async def user_stats(current_user: dict = Depends(_require_auth)):
    """Get aggregated statistics for the current user's dashboard."""
    user_id = int(current_user["id"])
    stats = get_user_stats(user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="User not found.")
    return stats


# ──────────────────────────────────────────────
# Query History
# ──────────────────────────────────────────────

@router.get("/query-history", response_model=QueryHistoryResponse)
async def query_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    current_user: dict = Depends(_require_auth),
):
    """Get paginated query history for the current user."""
    user_id = int(current_user["id"])
    return get_user_query_history(user_id, page=page, limit=limit)


# ──────────────────────────────────────────────
# Upload History
# ──────────────────────────────────────────────

@router.get("/uploads", response_model=list[UploadHistoryItem])
async def upload_history(current_user: dict = Depends(_require_auth)):
    """Get all file uploads for the current user."""
    user_id = int(current_user["id"])
    return get_user_uploads(user_id)


# ──────────────────────────────────────────────
# User Sessions
# ──────────────────────────────────────────────

@router.get("/sessions", response_model=list[UserSessionItem])
async def user_sessions(current_user: dict = Depends(_require_auth)):
    """Get all active data sessions for the current user."""
    user_id = int(current_user["id"])
    return get_user_sessions(user_id)
