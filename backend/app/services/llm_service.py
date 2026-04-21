"""
LLM Service — Single-call SQL generation.
Supports Groq (free tier) and Ollama (local) with auto-fallback.

Design:
- ONE LLM call per question → returns JSON {sql, explanation, assumptions}
- System prompt with schema context + conversation history
- Temperature = 0 for deterministic SQL output
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from app.config import settings
from app.services.schema_extractor import format_schema_for_llm


# ──────────────────────────────────────────────
# System Prompt Template
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert SQL analyst. You are given a SQLite database schema and a user's natural language question. Your job is to convert the question into a valid SQLite query and explain the results.

CRITICAL RULES:
1. Generate valid SQLite statements. You may use: SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE.
2. Use ONLY tables and columns from the provided schema (unless the user is creating a new table).
3. For SELECT queries, add LIMIT 100 unless the user explicitly asks for all data or the query uses aggregation (GROUP BY, COUNT, SUM, AVG, etc.).
4. Use double quotes for identifiers with special characters.
5. For ambiguous questions, make reasonable assumptions and document them.
6. Check if the user's question explicitly or implicitly asks for a chart, visualization, or plot. If they ask for "tabular form", "table only", or just ask a basic question without implying visualization, set wants_chart to false. Set it to true ONLY if they ask for a chart, graph, visualization, or if visual plotting is highly relevant.
7. Return ONLY a valid JSON object — no markdown, no code fences, no extra text.
8. For data-modifying queries (INSERT, UPDATE, DELETE, DROP, TRUNCATE), clearly explain what data will be changed in the explanation. Note: modifications happen on a copy of the database — the original data is preserved.
9. SQLite does not support TRUNCATE TABLE directly. Use DELETE FROM table_name instead.
10. NEVER use EXEC, EXECUTE, GRANT, REVOKE, ATTACH, DETACH, or PRAGMA.

RESPONSE FORMAT (strict JSON):
{
  "sql": "SQL statement here",
  "explanation": "One or two sentence explanation of what this query does and what the results mean, written for a non-technical user.",
  "assumptions": "Any assumptions made about ambiguous parts of the question, or empty string if none.",
  "wants_chart": boolean
}

DATABASE SCHEMA:
{schema}
"""


# ──────────────────────────────────────────────
# Abstract LLM Provider
# ──────────────────────────────────────────────

class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str) -> str:
        """Send prompt to LLM, return raw text response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...


# ──────────────────────────────────────────────
# Groq Provider (Free Tier)
# ──────────────────────────────────────────────

class GroqProvider(LLMProvider):
    """Groq API — free tier, ~500 tokens/sec."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client

    def is_available(self) -> bool:
        return bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "gsk_your_key_here")

    async def generate(self, system_prompt: str, user_message: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


# ──────────────────────────────────────────────
# Ollama Provider (Local, 100% Free)
# ──────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    """Ollama — runs locally, no API key needed."""

    def is_available(self) -> bool:
        try:
            import ollama
            ollama.list()
            return True
        except Exception:
            return False

    async def generate(self, system_prompt: str, user_message: str) -> str:
        import ollama
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            options={"temperature": 0},
            format="json",
        )
        return response["message"]["content"]


# ──────────────────────────────────────────────
# LLM Service (Main Interface)
# ──────────────────────────────────────────────

class LLMService:
    """
    Main LLM service — auto-detects available provider.
    Priority: Groq (fast, free) → Ollama (local, free)
    """

    def __init__(self):
        self._provider: LLMProvider | None = None
        self._providers = [GroqProvider(), OllamaProvider()]

    def _get_provider(self) -> LLMProvider:
        """Find first available provider."""
        if self._provider is not None:
            return self._provider

        for provider in self._providers:
            if provider.is_available():
                name = provider.__class__.__name__
                print(f"[OK] Using LLM provider: {name}")
                self._provider = provider
                return provider

        raise RuntimeError(
            "No LLM provider available!\n"
            "Options:\n"
            "  1. Set GROQ_API_KEY in .env (free: https://console.groq.com)\n"
            "  2. Install Ollama and pull a model (https://ollama.com)\n"
        )

    async def generate_sql(
        self,
        schema_tables: list[dict],
        question: str,
        chat_history: list[dict] | None = None,
        error_context: str | None = None,
    ) -> dict:
        """
        Generate SQL from natural language question.

        Args:
            schema_tables: Relevant table schemas (filtered by RAG)
            question: User's natural language question
            chat_history: Last N messages for context
            error_context: If retrying, the previous error + query

        Returns:
            dict with keys: sql, explanation, assumptions
        """
        provider = self._get_provider()

        # Build schema text
        schema_text = format_schema_for_llm(schema_tables)
        system = SYSTEM_PROMPT.replace("{schema}", schema_text)

        # Build user message with context
        user_msg = question

        # Add chat history context (last 5 messages)
        if chat_history:
            recent = chat_history[-5:]
            history_text = "\n".join(
                f"{msg['role'].upper()}: {msg['content']}" for msg in recent
            )
            user_msg = (
                f"CONVERSATION HISTORY:\n{history_text}\n\n"
                f"CURRENT QUESTION: {question}"
            )

        # Add error context for retry
        if error_context:
            user_msg += f"\n\nPREVIOUS ATTEMPT FAILED:\n{error_context}\nPlease fix the SQL and try again."

        # Call LLM
        raw_response = await provider.generate(system, user_msg)

        # Parse JSON response
        return _parse_llm_response(raw_response)


def _parse_llm_response(raw: str) -> dict:
    """
    Parse LLM response into structured dict.
    Handles cases where LLM wraps JSON in markdown code fences.
    """
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                return {
                    "sql": "",
                    "explanation": "Failed to parse LLM response.",
                    "assumptions": "",
                }
        else:
            return {
                "sql": "",
                "explanation": "Failed to parse LLM response.",
                "assumptions": "",
            }

    # Ensure required keys exist
    return {
        "sql": parsed.get("sql", "").strip(),
        "explanation": parsed.get("explanation", ""),
        "assumptions": parsed.get("assumptions", ""),
        "wants_chart": parsed.get("wants_chart", False),
    }


# Singleton
llm_service = LLMService()
