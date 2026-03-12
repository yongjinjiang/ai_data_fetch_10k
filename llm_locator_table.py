"""
LLM semantic locator for v4.
LLM identifies table/row/column for each field; Python reads numeric value.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


FIELD_RULES: dict[str, dict[str, Any]] = {
    "total_revenue": {
        "synonyms": [
            "total revenues", "total net revenues", "total net sales",
            "net revenues", "net sales", "sales to customers", "total net revenue"
        ],
        "table_hints": "Income statement / statements of operations. Prefer company-wide totals, avoid segments.",
    },
    "net_income": {
        "synonyms": [
            "net income", "net earnings", "net income (loss)",
            "net income attributable to common shareholders"
        ],
        "table_hints": "Income statement. Usually near bottom; avoid EPS rows.",
    },
    "total_assets": {
        "synonyms": ["total assets"],
        "table_hints": "Balance sheet. Use latest period column.",
    },
    "net_cash_from_operating_activities": {
        "synonyms": [
            "net cash provided by operating activities",
            "net cash from operating activities",
            "cash provided by operating activities",
            "cash generated from operations",
        ],
        "table_hints": "Cash flow statement. Must be operating activities (not investing/financing).",
    },
}

FIELDS = list(FIELD_RULES.keys())
_MAX_CHUNKS = 24
_MAX_CHUNK_CHARS = 1400


def _extract_json_block(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
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


def _select_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kws = set()
    for r in FIELD_RULES.values():
        for s in r["synonyms"]:
            kws.update(s.lower().split())
    kws.update({"income", "assets", "cash", "operating", "activities", "consolidated", "statements"})

    def score(ch: dict[str, Any]) -> int:
        txt = (ch.get("title", "") + " " + ch.get("serialized", "")).lower()
        return sum(1 for k in kws if k in txt)

    out = sorted(chunks, key=score, reverse=True)[:_MAX_CHUNKS]
    selected = []
    for ch in out:
        c = dict(ch)
        s = c.get("serialized", "")
        if len(s) > _MAX_CHUNK_CHARS:
            c["serialized"] = s[:_MAX_CHUNK_CHARS] + "\n...[truncated]"
        selected.append(c)
    return selected


def _build_prompt(ticker: str, chunks: list[dict[str, Any]]) -> str:
    schema = {
        f: {
            "table_id": 0,
            "row_label": "",
            "column_label": "",
            "confidence": 0.0,
            "reason": "",
        }
        for f in FIELDS
    }

    rules = []
    for f, meta in FIELD_RULES.items():
        rules.append(
            f"- {f}: synonyms={meta['synonyms']}; table_hints={meta['table_hints']}"
        )
    rules_text = "\n".join(rules)

    table_text = "\n\n".join(ch.get("serialized", "") for ch in chunks)

    return (
        f"You are locating financial fields in SEC 10-K tables for ticker {ticker}.\n"
        "IMPORTANT: Do NOT output numeric values. Only locate the most likely table/row/column labels.\n"
        "Return JSON only with this exact schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        "Rules:\n"
        "1) Choose the best table_id and semantic row/column labels.\n"
        "2) If table appears transposed, still provide best row_label and column_label as they appear.\n"
        "3) If unsure, set table_id=null, row_label=null, column_label=null, confidence=0.0.\n"
        "4) confidence must be between 0 and 1.\n\n"
        f"Field hints:\n{rules_text}\n\n"
        f"Tables:\n{table_text}"
    )


def _empty() -> dict[str, dict[str, Any]]:
    return {
        f: {
            "table_id": None,
            "row_label": None,
            "column_label": None,
            "confidence": 0.0,
            "reason": None,
            "used_llm": False,
        }
        for f in FIELDS
    }


def locate_fields_with_llm_table(ticker: str, chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    empty = _empty()
    if not chunks:
        return empty

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return empty

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _build_prompt(ticker, _select_chunks(chunks))

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Output valid JSON only."},
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

    out: dict[str, dict[str, Any]] = {}
    for f in FIELDS:
        obj = parsed.get(f, {}) if isinstance(parsed, dict) else {}
        if not isinstance(obj, dict):
            obj = {}

        tid = obj.get("table_id")
        try:
            tid = int(tid) if tid is not None else None
        except Exception:
            tid = None

        conf = obj.get("confidence", 0.0)
        try:
            conf = float(conf)
        except Exception:
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        out[f] = {
            "table_id": tid,
            "row_label": obj.get("row_label") or None,
            "column_label": obj.get("column_label") or None,
            "confidence": conf,
            "reason": obj.get("reason") or None,
            "used_llm": True,
        }
    return out
