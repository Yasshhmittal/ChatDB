"""
Chart Service — Rule-Based Chart Type Detection.
No LLM calls. Pure Python heuristics based on column types and data shape.

Rules:
- date/time column + numeric → line chart
- categorical + numeric → bar chart (or pie if ≤ 6 categories)
- two numeric columns → scatter plot
- single numeric aggregate → no chart (just a number)
"""

from __future__ import annotations

import re
from typing import Any

# Common date-like column names
_DATE_PATTERNS = re.compile(
    r"(date|time|year|month|day|created|updated|timestamp|_at$|_on$)",
    re.IGNORECASE,
)

# Color palette for chart datasets (vibrant, premium feel)
CHART_COLORS = [
    "rgba(99, 102, 241, 0.8)",    # indigo
    "rgba(244, 63, 94, 0.8)",     # rose
    "rgba(34, 197, 94, 0.8)",     # green
    "rgba(251, 146, 60, 0.8)",    # orange
    "rgba(139, 92, 246, 0.8)",    # violet
    "rgba(14, 165, 233, 0.8)",    # sky
    "rgba(236, 72, 153, 0.8)",    # pink
    "rgba(245, 158, 11, 0.8)",    # amber
]

CHART_BORDER_COLORS = [
    "rgba(99, 102, 241, 1)",
    "rgba(244, 63, 94, 1)",
    "rgba(34, 197, 94, 1)",
    "rgba(251, 146, 60, 1)",
    "rgba(139, 92, 246, 1)",
    "rgba(14, 165, 233, 1)",
    "rgba(236, 72, 153, 1)",
    "rgba(245, 158, 11, 1)",
]


def detect_chart(columns: list[str], data: list[dict[str, Any]]) -> dict | None:
    """
    Analyze query results and suggest a chart configuration.

    Args:
        columns: Column names from the query result
        data: List of row dicts

    Returns:
        ChartConfig dict or None if no chart is appropriate
    """
    if not data or not columns or len(data) < 2:
        return None  # not enough data for a chart

    if len(columns) < 2:
        return None  # need at least 2 columns for a meaningful chart

    if len(data) > 100:
        # Too many data points — truncate for chart readability
        data = data[:50]

    # Classify columns
    numeric_cols = [c for c in columns if _is_numeric(data, c)]
    date_cols = [c for c in columns if _is_date_like(c, data)]
    cat_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

    # ── Rule 1: Time series → line chart ──
    if date_cols and numeric_cols:
        x_col = date_cols[0]
        y_col = numeric_cols[0]
        return _build_chart("line", data, x_col, [y_col])

    # ── Rule 2: Category + numeric → bar or pie ──
    if cat_cols and numeric_cols:
        x_col = cat_cols[0]
        y_col = numeric_cols[0]
        n_categories = len(set(str(row.get(x_col, "")) for row in data))

        if n_categories <= 6 and len(numeric_cols) == 1:
            return _build_chart("pie", data, x_col, [y_col])
        else:
            return _build_chart("bar", data, x_col, numeric_cols[:3])

    # ── Rule 3: Two numeric columns → scatter ──
    if len(numeric_cols) >= 2:
        return _build_scatter(data, numeric_cols[0], numeric_cols[1])

    # ── Rule 4: First column as label, rest as values ──
    if len(columns) >= 2 and numeric_cols:
        label_col = columns[0] if columns[0] not in numeric_cols else cat_cols[0] if cat_cols else columns[0]
        return _build_chart("bar", data, label_col, numeric_cols[:3])

    return None


def _build_chart(
    chart_type: str,
    data: list[dict],
    label_col: str,
    value_cols: list[str],
) -> dict:
    """Build a chart configuration dict."""
    labels = [str(row.get(label_col, "")) for row in data]

    datasets = []
    for i, col in enumerate(value_cols):
        color_idx = i % len(CHART_COLORS)
        values = []
        for row in data:
            val = row.get(col)
            try:
                values.append(float(val) if val is not None else 0)
            except (ValueError, TypeError):
                values.append(0)

        dataset = {
            "label": col,
            "data": values,
            "backgroundColor": (
                [CHART_COLORS[j % len(CHART_COLORS)] for j in range(len(values))]
                if chart_type == "pie"
                else CHART_COLORS[color_idx]
            ),
            "borderColor": (
                [CHART_BORDER_COLORS[j % len(CHART_BORDER_COLORS)] for j in range(len(values))]
                if chart_type == "pie"
                else CHART_BORDER_COLORS[color_idx]
            ),
            "borderWidth": 2,
        }

        if chart_type == "line":
            dataset["fill"] = False
            dataset["tension"] = 0.3

        datasets.append(dataset)

    return {
        "chart_type": chart_type,
        "labels": labels,
        "datasets": datasets,
        "x_label": label_col,
        "y_label": value_cols[0] if value_cols else "",
    }


def _build_scatter(data: list[dict], x_col: str, y_col: str) -> dict:
    """Build scatter plot configuration."""
    points = []
    for row in data:
        try:
            x = float(row.get(x_col, 0))
            y = float(row.get(y_col, 0))
            points.append({"x": x, "y": y})
        except (ValueError, TypeError):
            continue

    return {
        "chart_type": "scatter",
        "labels": [],
        "datasets": [{
            "label": f"{x_col} vs {y_col}",
            "data": points,
            "backgroundColor": CHART_COLORS[0],
            "borderColor": CHART_BORDER_COLORS[0],
            "borderWidth": 1,
        }],
        "x_label": x_col,
        "y_label": y_col,
    }


def _is_numeric(data: list[dict], col: str) -> bool:
    """Check if a column contains mostly numeric values."""
    numeric_count = 0
    total = min(len(data), 20)  # sample first 20 rows

    for row in data[:total]:
        val = row.get(col)
        if val is None:
            continue
        try:
            float(val)
            numeric_count += 1
        except (ValueError, TypeError):
            pass

    return numeric_count > total * 0.7  # >70% numeric


def _is_date_like(col: str, data: list[dict]) -> bool:
    """Check if a column name suggests date/time data."""
    if _DATE_PATTERNS.search(col):
        return True

    # Also check first few values for date-like patterns
    date_pattern = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")
    for row in data[:5]:
        val = str(row.get(col, ""))
        if date_pattern.search(val):
            return True

    return False
