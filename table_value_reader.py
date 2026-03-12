"""
Deterministic table value reader for v4.
Given table chunks + LLM-provided (table_id, row_label, column_label),
read the numeric cell in Python (no LLM numeric output).
"""

from __future__ import annotations

import re
from typing import Any


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _sim(a: str, b: str) -> float:
    """Cheap token-overlap similarity in [0,1]."""
    a_n, b_n = _norm(a), _norm(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0
    ta, tb = set(a_n.split()), set(b_n.split())
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def parse_number(text: str) -> float | None:
    if not text:
        return None
    t = text.strip()
    if t in ("", "-", "—", "–", "$", "(", ")", "%"):
        return None

    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]

    t = t.replace(",", "").replace("$", "").replace("\xa0", " ").strip()
    if not t or t.endswith("%"):
        return None

    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _best_col_idx(header_rows: list[list[str]], column_label: str | None, row: list[str]) -> int | None:
    # Prefer header match if column_label provided
    if column_label and header_rows:
        best_idx, best_score = None, 0.0
        for hr in header_rows:
            for i, c in enumerate(hr):
                score = _sim(c, column_label)
                if score > best_score:
                    best_idx, best_score = i, score
        if best_idx is not None and best_score >= 0.5:
            return best_idx

    # Fallback: first numeric in row after label cell
    for i, c in enumerate(row[1:], start=1):
        if parse_number(c) is not None:
            return i
    return None


def _best_row(rows: list[list[str]], row_label: str | None) -> tuple[int | None, list[str] | None]:
    if not rows:
        return None, None

    if row_label:
        best_i, best_score = None, 0.0
        for i, r in enumerate(rows):
            if not r:
                continue
            # first-cell label priority
            score1 = _sim(r[0], row_label)
            # fallback: any cell contains label-like text
            score2 = max((_sim(c, row_label) for c in r), default=0.0)
            score = max(score1, score2 * 0.85)
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 0.45:
            return best_i, rows[best_i]

    # Fallback: pick first row that has a numeric cell after first column
    for i, r in enumerate(rows):
        if any(parse_number(c) is not None for c in r[1:]):
            return i, r
    return None, None


def read_value_from_chunks(
    chunks: list[dict[str, Any]],
    table_id: int | None,
    row_label: str | None,
    column_label: str | None,
) -> tuple[float | None, dict[str, Any]]:
    """
    Returns (value, debug).
    """
    if table_id is None:
        return None, {"reason": "table_id_missing"}

    target = None
    for ch in chunks:
        if ch.get("table_id") == table_id:
            target = ch
            break
    if not target:
        return None, {"reason": "table_not_found", "table_id": table_id}

    rows = target.get("rows", []) or []
    header_rows = target.get("header_rows", []) or []

    row_idx, row = _best_row(rows, row_label)
    if row is None:
        return None, {"reason": "row_not_found", "table_id": table_id, "row_label": row_label}

    col_idx = _best_col_idx(header_rows, column_label, row)
    if col_idx is None or col_idx >= len(row):
        return None, {
            "reason": "column_not_found",
            "table_id": table_id,
            "row_idx": row_idx,
            "column_label": column_label,
        }

    v = parse_number(row[col_idx])
    if v is None:
        return None, {
            "reason": "cell_not_numeric",
            "table_id": table_id,
            "row_idx": row_idx,
            "col_idx": col_idx,
            "cell": row[col_idx],
        }

    return v, {
        "table_id": table_id,
        "row_idx": row_idx,
        "col_idx": col_idx,
        "row_label": row_label,
        "column_label": column_label,
        "cell": row[col_idx],
    }
