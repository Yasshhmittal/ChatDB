"""
RAG Schema Filter Service.
Uses local embeddings to select only relevant tables for the LLM prompt.

Flow:
1. On upload: embed each table description → store in memory
2. On question: embed question → cosine similarity → top-K tables
3. Skip filtering if database has ≤ threshold tables (not worth the overhead)

Embedding model: all-MiniLM-L6-v2 (80MB, runs locally, free)
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.services.schema_extractor import get_table_descriptions, extract_schema

# Lazy-load the embedding model (heavy import, ~80MB download on first use)
_model = None
_embeddings_cache: dict[str, dict[str, np.ndarray]] = {}  # session_id → {table_name: embedding}


def _get_model():
    """Lazy-load sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print(f"[OK] Loaded embedding model: {settings.EMBEDDING_MODEL}")
    return _model


def build_embeddings(session_id: str) -> None:
    """
    Generate and cache embeddings for all tables in a session's database.
    Called once after file upload.
    """
    descriptions = get_table_descriptions(session_id)

    if not descriptions:
        return

    model = _get_model()
    table_names = list(descriptions.keys())
    texts = list(descriptions.values())

    # Batch encode all table descriptions
    embeddings = model.encode(texts, normalize_embeddings=True)

    _embeddings_cache[session_id] = {
        name: emb for name, emb in zip(table_names, embeddings)
    }


def get_relevant_tables(session_id: str, question: str) -> list[dict]:
    """
    Find the most relevant tables for a user question.

    If total tables ≤ threshold, returns ALL tables (RAG overhead not worth it).
    Otherwise, uses cosine similarity to find top-K relevant tables.

    Returns: list of table schema dicts (same format as extract_schema)
    """
    full_schema = extract_schema(session_id)
    total_tables = len(full_schema)

    # Skip RAG for small databases — just send everything
    if total_tables <= settings.RAG_MIN_TABLES_FOR_FILTERING:
        return full_schema

    # Check if embeddings are cached
    if session_id not in _embeddings_cache:
        build_embeddings(session_id)

    cached = _embeddings_cache.get(session_id)
    if not cached:
        return full_schema  # fallback: send all

    model = _get_model()

    # Embed the question
    question_emb = model.encode([question], normalize_embeddings=True)

    # Calculate similarity with each table
    table_names = list(cached.keys())
    table_embs = np.array([cached[name] for name in table_names])

    similarities = cosine_similarity(question_emb, table_embs)[0]

    # Get top-K most relevant tables
    top_k = min(settings.RAG_TOP_K, total_tables)
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    relevant_names = {table_names[i] for i in top_indices}

    # Filter full schema to only relevant tables
    return [t for t in full_schema if t["name"] in relevant_names]


def clear_session_cache(session_id: str) -> None:
    """Remove cached embeddings for a session (cleanup)."""
    _embeddings_cache.pop(session_id, None)
