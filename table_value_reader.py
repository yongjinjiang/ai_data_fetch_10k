"""
Deterministic table value reader for v4.
Given table chunks + LLM-provided (table_id, row_label, column_label),
read the numeric cell in Python (no LLM numeric output).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _canonical_tokens(s: str | None) -> set[str]:
    txt = _norm(s)
    if not txt:
        return set()
    stop = {
        "the", "and", "of", "to", "in", "for", "by", "from", "provided", "used",
        "activities", "activity", "statement", "statements", "consolidated", "total",
    }
    return {t for t in txt.split() if t and t not in stop}


def _sim(a: str, b: str) -> float:
    """Hybrid similarity in [0,1]: token overlap + sequence similarity."""
    a_n, b_n = _norm(a), _norm(b)
    if not a_n or not b_n:
        return 0.0
    if a_n == b_n:
        return 1.0

    ta, tb = _canonical_tokens(a), _canonical_tokens(b)
    j = (len(ta & tb) / len(ta | tb)) if (ta and tb and (ta | tb)) else 0.0
    seq = SequenceMatcher(None, a_n, b_n).ratio()
    return 0.65 * j + 0.35 * seq


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


def _build_column_headers(header_rows: list[list[str]], rows: list[list[str]]) -> dict[int, str]:
    """Compose multi-line column headers by stacking header rows + first top row."""
    cols: dict[int, list[str]] = {}
    source_rows = list(header_rows)
    if rows:
        source_rows = source_rows + [rows[0]]

    for r in source_rows:
        for i, c in enumerate(r):
            t = _norm(c)
            if t:
                cols.setdefault(i, []).append(t)

    return {i: " ".join(parts) for i, parts in cols.items()}


def _infer_latest_year_col_idx(header_rows: list[list[str]], rows: list[list[str]]) -> int | None:
    year_re = re.compile(r"(19|20)\d{2}")
    best_year = -1
    best_idx = None

    col_headers = _build_column_headers(header_rows, rows)
    for i, txt in col_headers.items():
        years = [int(m.group(0)) for m in year_re.finditer(txt)]
        if years:
            y = max(years)
            if y > best_year:
                best_year = y
                best_idx = i

    # fallback from raw cells
    if best_idx is None:
        for r in list(header_rows) + rows[:3]:
            for i, c in enumerate(r):
                t = _norm(c)
                if year_re.fullmatch(t):
                    y = int(t)
                    if y > best_year:
                        best_year = y
                        best_idx = i
    return best_idx


def _best_col_idx(
    header_rows: list[list[str]],
    rows: list[list[str]],
    column_label: str | None,
    row: list[str],
) -> int | None:
    # Prefer explicit column label match against composed multi-line headers
    if column_label:
        best_idx, best_score = None, 0.0
        col_headers = _build_column_headers(header_rows, rows)
        for i, c in col_headers.items():
            score = _sim(c, column_label)
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx is not None and best_score >= 0.45:
            return best_idx

    # If no label or weak label, infer latest fiscal year column from header/top rows
    yr_idx = _infer_latest_year_col_idx(header_rows, rows)
    if yr_idx is not None:
        return yr_idx

    # Fallback: first numeric in row after label cell
    for i, c in enumerate(row[1:], start=1):
        if parse_number(c) is not None:
            return i
    return None


def _resolve_numeric_in_row_near_col(row: list[str], col_idx: int) -> tuple[float | None, int | None]:
    # Try exact col first, then search right/left neighbors for numeric cell
    probe_order = [0, 1, -1, 2, -2, 3, -3]
    for d in probe_order:
        j = col_idx + d
        if 0 <= j < len(row):
            v = parse_number(row[j])
            if v is not None:
                return v, j
    return None, None


def _row_label_text(row: list[str]) -> str:
    """Compose row label from leading non-numeric cells (handles split labels)."""
    parts: list[str] = []
    for c in row:
        if parse_number(c) is not None:
            break
        t = _norm(c)
        if t:
            parts.append(t)
        if len(parts) >= 4:
            break
    return " ".join(parts) if parts else _norm(row[0] if row else "")


def _best_row(rows: list[list[str]], row_label: str | None) -> tuple[int | None, list[str] | None]:
    if not rows:
        return None, None

    if row_label:
        best_i, best_score = None, 0.0
        for i, r in enumerate(rows):
            if not r:
                continue
            row_head = _row_label_text(r)
            score_head = _sim(row_head, row_label)
            score_first = _sim(r[0], row_label)
            score_any = max((_sim(c, row_label) for c in r), default=0.0)
            has_num = any(parse_number(c) is not None for c in r[1:])
            score = 0.60 * score_head + 0.20 * score_first + 0.20 * score_any + (0.05 if has_num else 0.0)
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 0.38:
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

    col_idx = _best_col_idx(header_rows, rows, column_label, row)
    if col_idx is None or col_idx >= len(row):
        return None, {
            "reason": "column_not_found",
            "table_id": table_id,
            "row_idx": row_idx,
            "column_label": column_label,
        }

    v, resolved_col = _resolve_numeric_in_row_near_col(row, col_idx)
    if v is None or resolved_col is None:
        return None, {
            "reason": "cell_not_numeric",
            "table_id": table_id,
            "row_idx": row_idx,
            "col_idx": col_idx,
            "cell": row[col_idx] if 0 <= col_idx < len(row) else None,
        }

    return v, {
        "table_id": table_id,
        "row_idx": row_idx,
        "col_idx": resolved_col,
        "row_label": row_label,
        "column_label": column_label,
        "cell": row[resolved_col],
    }


def read_value_across_chunks(
    chunks: list[dict[str, Any]],
    row_label: str | None,
    column_label: str | None,
) -> tuple[float | None, dict[str, Any]]:
    """Fallback reader: search all chunks for best row-label match and read value."""
    if not row_label:
        return None, {"reason": "row_label_missing"}

    best: dict[str, Any] | None = None

    for ch in chunks:
        rows = ch.get("rows", []) or []
        if not rows:
            continue
        header_rows = ch.get("header_rows", []) or []

        row_idx, row = _best_row(rows, row_label)
        if row is None:
            continue

        row_head = _row_label_text(row)
        row_score = _sim(row_head, row_label)
        if row_score < 0.38:
            continue

        col_idx = _best_col_idx(header_rows, rows, column_label, row)
        if col_idx is None:
            continue

        v, resolved_col = _resolve_numeric_in_row_near_col(row, col_idx)
        if v is None or resolved_col is None:
            continue

        cand = {
            "value": v,
            "table_id": ch.get("table_id"),
            "row_idx": row_idx,
            "col_idx": resolved_col,
            "row_score": row_score,
            "cell": row[resolved_col],
        }

        if best is None:
            best = cand
            continue

        # Prefer better semantic match first, then larger magnitude (often total rows)
        if (cand["row_score"] > best["row_score"] + 0.03) or (
            abs(cand["row_score"] - best["row_score"]) <= 0.03 and abs(cand["value"]) > abs(best["value"])
        ):
            best = cand

    if not best:
        return None, {"reason": "global_fallback_not_found", "row_label": row_label}

    return best["value"], {
        "reason": "global_fallback",
        "table_id": best["table_id"],
        "row_idx": best["row_idx"],
        "col_idx": best["col_idx"],
        "row_label": row_label,
        "column_label": column_label,
        "row_score": round(best["row_score"], 3),
        "cell": best["cell"],
    }
