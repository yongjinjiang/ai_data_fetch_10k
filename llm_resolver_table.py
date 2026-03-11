"""
Table-centric LLM resolver for v3 extraction.

Builds prompts from table chunks (not the whole filing) and includes
soft-rule instructions covering field synonyms and table/column semantics.

Returns per-field structured JSON:
  {
    "value": float | null,
    "table_id": int | null,
    "row_label": str | null,
    "column_label": str | null,
    "unit": str | null,
    "confidence": float,       # 0.0 – 1.0
    "source_label": str | null,
    "used_llm": bool
  }

Gracefully returns empty outputs when OPENAI_API_KEY is missing or API fails.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Field metadata: synonyms + column / table semantics used in soft rules
# ---------------------------------------------------------------------------

FIELD_SOFT_RULES: dict[str, dict[str, Any]] = {
    "total_revenue": {
        "synonyms": [
            "total revenues", "total net revenues", "total net sales",
            "net revenues", "net sales", "revenues", "sales to customers",
            "total net revenue", "total revenues and other income",
        ],
        "column_hints": "Look for the most-recent fiscal year column (usually leftmost data column).",
        "table_hints": (
            "Income statement / consolidated statements of operations / "
            "consolidated statements of income. Avoid segment subtotals."
        ),
        "unit_hints": "Usually reported in millions USD. Occasionally billions — check scale note.",
    },
    "net_income": {
        "synonyms": [
            "net income", "net earnings", "net income (loss)",
            "net earnings from continuing operations",
            "net income attributable to common shareholders",
            "profit for the year",
        ],
        "column_hints": "Most-recent fiscal year column. Negative values (losses) are valid.",
        "table_hints": (
            "Income statement. Look near the bottom of the table, after operating income. "
            "Do NOT use 'basic EPS' or per-share lines."
        ),
        "unit_hints": "Millions USD. Can be negative (net loss).",
    },
    "total_assets": {
        "synonyms": [
            "total assets", "total assets and other", "assets total",
        ],
        "column_hints": "End-of-period (most recent) balance sheet column.",
        "table_hints": (
            "Balance sheet / consolidated balance sheets. "
            "Sum of current + non-current assets; usually the largest figure on the asset side."
        ),
        "unit_hints": "Millions USD. Typically very large (often > 100,000 for large-cap).",
    },
}

FIELDS = list(FIELD_SOFT_RULES.keys())

# Maximum number of table chunks sent to LLM per call (avoid token overflow)
_MAX_CHUNKS = 20
# Maximum serialized characters per chunk
_MAX_CHUNK_CHARS = 1_200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Parse JSON from plain text or fenced markdown."""
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    m2 = re.search(r"(\{[\s\S]*\})", text)
    if m2:
        try:
            obj = json.loads(m2.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _select_relevant_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Select the most relevant table chunks for the target fields.

    Scoring: chunks whose title or first few rows contain field-related
    keywords score higher.  We keep at most _MAX_CHUNKS chunks and truncate
    each serialized representation to _MAX_CHUNK_CHARS characters.
    """
    keyword_set: set[str] = set()
    for meta in FIELD_SOFT_RULES.values():
        for syn in meta["synonyms"]:
            keyword_set.update(syn.lower().split())
    # Also add structural cues
    keyword_set.update({"income", "revenue", "assets", "earnings", "operations",
                         "balance", "financial", "consolidated", "statements"})

    def _score(chunk: dict[str, Any]) -> int:
        text = (chunk.get("title", "") + " " + chunk.get("serialized", "")).lower()
        return sum(1 for kw in keyword_set if kw in text)

    scored = sorted(chunks, key=_score, reverse=True)
    selected = scored[:_MAX_CHUNKS]
    # Truncate serialized text
    for ch in selected:
        if len(ch.get("serialized", "")) > _MAX_CHUNK_CHARS:
            ch = dict(ch)  # shallow copy so original is untouched
            ch["serialized"] = ch["serialized"][:_MAX_CHUNK_CHARS] + "\n...[truncated]"
    return selected


def _build_prompt(ticker: str, chunks: list[dict[str, Any]]) -> str:
    """Build the LLM prompt from table chunks and soft-rule instructions."""
    output_schema = {
        field: {
            "value": 0.0,
            "table_id": 0,
            "row_label": "",
            "column_label": "",
            "unit": "millions USD",
            "confidence": 0.0,
            "source_label": "",
        }
        for field in FIELDS
    }

    soft_rules_text = ""
    for field, meta in FIELD_SOFT_RULES.items():
        syns = ", ".join(f'"{s}"' for s in meta["synonyms"])
        soft_rules_text += (
            f"\n## {field}\n"
            f"  Synonyms: {syns}\n"
            f"  Column guidance: {meta['column_hints']}\n"
            f"  Table guidance: {meta['table_hints']}\n"
            f"  Unit guidance: {meta['unit_hints']}\n"
        )

    table_text = "\n\n".join(ch["serialized"] for ch in chunks)

    return (
        f"You are a financial data extraction expert analyzing an SEC 10-K filing for {ticker}.\n"
        "Your task: extract three financial metrics from the tables below.\n\n"
        "## Soft Rules\n"
        "Apply these rules when choosing the correct row and column:\n"
        + soft_rules_text
        + "\n## Output Schema\n"
        "Return ONLY valid JSON matching this schema exactly (no extra keys, no markdown):\n"
        + json.dumps(output_schema, indent=2)
        + "\n\nField guidance:\n"
        "- value: numeric value in millions USD (null if not found)\n"
        "- table_id: the [TABLE N] index where the value was found\n"
        "- row_label: the exact row label text from the table\n"
        "- column_label: the column header text (year or period), if available\n"
        "- unit: inferred unit ('millions USD', 'billions USD', etc.)\n"
        "- confidence: 0.0–1.0 (0.95+ for clear labeled totals, 0.5 for uncertain)\n"
        "- source_label: same as row_label\n\n"
        "If a field cannot be found, set value to null and confidence to 0.0.\n\n"
        "## Tables\n"
        + table_text
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _empty_result() -> dict[str, dict[str, Any]]:
    return {
        f: {
            "value": None,
            "table_id": None,
            "row_label": None,
            "column_label": None,
            "unit": None,
            "confidence": 0.0,
            "source_label": None,
            "used_llm": False,
        }
        for f in FIELDS
    }


def resolve_fields_with_llm_table(
    ticker: str,
    chunks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Resolve financial fields using table chunks as LLM context.

    Returns empty outputs (used_llm=False) when:
      - OPENAI_API_KEY environment variable is not set
      - API call fails for any reason
    """
    empty = _empty_result()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return empty

    if not chunks:
        return empty

    relevant = _select_relevant_chunks(chunks)
    prompt = _build_prompt(ticker, relevant)

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Output valid JSON only. No markdown, no explanation."},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json_block(content) or {}
    except Exception:
        return empty

    result: dict[str, dict[str, Any]] = {}
    for field in FIELDS:
        obj = parsed.get(field, {}) if isinstance(parsed, dict) else {}
        if not isinstance(obj, dict):
            obj = {}

        # value
        val = obj.get("value")
        try:
            val = float(val) if val is not None else None
        except (TypeError, ValueError):
            val = None

        # confidence
        conf = obj.get("confidence", 0.0)
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        # table_id
        tid = obj.get("table_id")
        try:
            tid = int(tid) if tid is not None else None
        except (TypeError, ValueError):
            tid = None

        result[field] = {
            "value": val,
            "table_id": tid,
            "row_label": obj.get("row_label") or None,
            "column_label": obj.get("column_label") or None,
            "unit": obj.get("unit") or None,
            "confidence": conf,
            "source_label": obj.get("source_label") or obj.get("row_label") or None,
            "used_llm": True,
        }

    return result
