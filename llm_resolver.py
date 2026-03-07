"""
Optional LLM resolver for hybrid extraction.
Uses OpenAI-compatible Chat Completions via HTTP when OPENAI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Parse JSON from plain text or fenced markdown."""
    text = text.strip()
    if not text:
        return None

    # Direct JSON first
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Fenced code block
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            return None

    # Fallback: first {...} block
    m2 = re.search(r"(\{[\s\S]*\})", text)
    if m2:
        try:
            obj = json.loads(m2.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            return None
    return None


def _build_prompt(ticker: str, candidates: dict[str, list[dict[str, Any]]]) -> str:
    schema = {
        "total_revenue": {"value": 0, "confidence": 0.0, "source_label": ""},
        "net_income": {"value": 0, "confidence": 0.0, "source_label": ""},
        "total_assets": {"value": 0, "confidence": 0.0, "source_label": ""},
    }
    return (
        "You are extracting financial statement fields from 10-K candidate rows. "
        "Pick best value for each field based only on candidates. "
        "Return ONLY JSON matching this schema keys exactly: "
        + json.dumps(schema)
        + "\nTicker: "
        + ticker
        + "\nCandidates: "
        + json.dumps(candidates, ensure_ascii=False)
        + "\nRules: confidence between 0 and 1. If unknown, set value to null and confidence 0."
    )


def resolve_fields_with_llm(ticker: str, candidates: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """
    Resolve fields using LLM if OPENAI_API_KEY exists.
    Returns per-field dict with value/confidence/source_label and resolution metadata.
    """
    fields = ["total_revenue", "net_income", "total_assets"]
    empty = {f: {"value": None, "confidence": 0.0, "source_label": None, "used_llm": False} for f in fields}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return empty

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "Output valid JSON only.",
            },
            {
                "role": "user",
                "content": _build_prompt(ticker, candidates),
            },
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
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json_block(content) or {}
    except Exception:
        return empty

    result = {}
    for f in fields:
        obj = parsed.get(f, {}) if isinstance(parsed, dict) else {}
        val = obj.get("value")
        conf = obj.get("confidence", 0.0)
        src = obj.get("source_label")

        try:
            val = float(val) if val is not None else None
        except Exception:
            val = None

        try:
            conf = float(conf)
        except Exception:
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        result[f] = {
            "value": val,
            "confidence": conf,
            "source_label": src,
            "used_llm": True,
        }

    return result
