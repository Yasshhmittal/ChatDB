"""
FastAPI application entry point.
Chat with Database (SQL + LLM) — Production Server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import upload, chat, schema, auth, download
from app.auth_db import init_db


# ──────────────────────────────────────────────
# Lifecycle
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup: ensure directories exist
    settings.ensure_dirs()
    # Initialize application database for users
    init_db()
    print("[OK] Chat with Database backend started")
    print(f"   Data dir:   {settings.DATA_DIR}")
    print(f"   Upload dir: {settings.UPLOAD_DIR}")
    print(f"   Groq key:   {'configured' if settings.GROQ_API_KEY else 'NOT SET'}")
    yield
    # Shutdown
    print("[BYE] Server shutting down")


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Chat with Database",
    description="Ask questions about your data in natural language. Powered by LLM.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow React frontend
# In production, set FRONTEND_URL to your Vercel/Netlify/etc domain or "*"
allow_origins = [url.strip() for url in settings.FRONTEND_URL.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────

app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(schema.router, prefix="/api", tags=["Schema"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(download.router, prefix="/api", tags=["Download"])


# ──────────────────────────────────────────────
# Global error handler
# ──────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all error handler — never expose stack traces to client."""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Quick health check endpoint."""
    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY),
    }
