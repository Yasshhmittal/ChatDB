"""
Configuration management using pydantic-settings.
Loads from .env file with sensible defaults.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # --- LLM ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- Database ---
    DATABASE_URL: str = ""

    # --- Paths ---
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./uploads"

    # --- Network / Deploy ---
    FRONTEND_URL: str = "http://localhost:5173"

    # --- Limits ---
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_RESULT_ROWS: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 5
    MAX_RETRY_ATTEMPTS: int = 3

    # --- RAG ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_TOP_K: int = 5
    RAG_MIN_TABLES_FOR_FILTERING: int = 10  # Skip RAG if fewer tables

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self) -> None:
        """Create data and upload directories if they don't exist."""
        Path(self.DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
