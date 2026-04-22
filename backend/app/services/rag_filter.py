"""
RAG Schema Filter Service.
Uses TF-IDF to select only relevant tables for the LLM prompt.

Flow:
1. On upload: fit TfidfVectorizer on table descriptions → store in memory
2. On question: transform question → cosine similarity → top-K tables
3. Skip filtering if database has ≤ threshold tables (not worth the overhead)

Embedding model: scikit-learn TfidfVectorizer (Lightweight, solves OOM issues)
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.services.schema_extractor import get_table_descriptions, extract_schema

# Cache the vectorizer and the TF-IDF matrix for each session
_vectorizer_cache: dict[str, tuple[TfidfVectorizer, list[str], np.ndarray]] = {}


def build_embeddings(session_id: str) -> None:
    """
    Generate and cache TF-IDF vectors for all tables in a session's database.
    Called once after file upload or when needed.
    """
    descriptions = get_table_descriptions(session_id)

    if not descriptions:
        return

    table_names = list(descriptions.keys())
    texts = list(descriptions.values())

    vectorizer = TfidfVectorizer(stop_words='english')
    # Fit and transform the table descriptions
    tfidf_matrix = vectorizer.fit_transform(texts)

    _vectorizer_cache[session_id] = (vectorizer, table_names, tfidf_matrix)


def get_relevant_tables(session_id: str, question: str) -> list[dict]:
    """
    Find the most relevant tables for a user question.

    If total tables ≤ threshold, returns ALL tables (RAG overhead not worth it).
    Otherwise, uses TF-IDF cosine similarity to find top-K relevant tables.

    Returns: list of table schema dicts (same format as extract_schema)
    """
    full_schema = extract_schema(session_id)
    total_tables = len(full_schema)

    # Skip RAG for small databases — just send everything
    if total_tables <= settings.RAG_MIN_TABLES_FOR_FILTERING:
        return full_schema

    # Check if vectors are cached
    if session_id not in _vectorizer_cache:
        build_embeddings(session_id)

    cached = _vectorizer_cache.get(session_id)
    if not cached:
        return full_schema  # fallback: send all

    vectorizer, table_names, tfidf_matrix = cached

    # Transform the question using the fitted vectorizer
    question_vec = vectorizer.transform([question])

    # Calculate similarity with each table
    similarities = cosine_similarity(question_vec, tfidf_matrix)[0]

    # Get top-K most relevant tables
    top_k = min(settings.RAG_TOP_K, total_tables)
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    relevant_names = {table_names[i] for i in top_indices}

    # Filter full schema to only relevant tables
    return [t for t in full_schema if t["name"] in relevant_names]


def clear_session_cache(session_id: str) -> None:
    """Remove cached vectors for a session (cleanup)."""
    _vectorizer_cache.pop(session_id, None)
