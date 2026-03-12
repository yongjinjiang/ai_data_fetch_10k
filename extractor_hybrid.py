"""
Hybrid extractor: rule-based v2 + optional LLM resolver + validator fallback.
"""

from __future__ import annotations

import os
from typing import Any

from candidate_finder import find_candidates_for_ticker
from config import COMPANIES, DATA_DIR
from extractor_v2 import extract_filing_v2
from llm_resolver import resolve_fields_with_llm
from validator import decide_value


FIELDS = ["total_revenue", "net_income", "total_assets", "net_cash_from_operating_activities"]


def extract_all_hybrid() -> tuple[dict[str, dict[str, float | None]], dict[str, Any]]:
    """
    Returns:
      - extracted: {ticker: {field: final_value}}
      - debug: {ticker: {rule, llm, decisions, candidates}}
    """
    extracted: dict[str, dict[str, float | None]] = {}
    debug: dict[str, Any] = {}

    for ticker in COMPANIES:
        filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
        if not os.path.exists(filepath):
            extracted[ticker] = {f: None for f in FIELDS}
            debug[ticker] = {
                "error": "file_missing",
                "rule": {f: None for f in FIELDS},
                "llm": {f: {"value": None, "confidence": 0.0, "source_label": None, "used_llm": False} for f in FIELDS},
                "decisions": {f: {"value": None, "source": "none", "reason": "file_missing"} for f in FIELDS},
                "candidates": {f: [] for f in FIELDS},
            }
            continue

        print(f"  [{ticker}] Extracting (hybrid)...")
        rule_res = extract_filing_v2(filepath)
        candidates = find_candidates_for_ticker(ticker)
        llm_res = resolve_fields_with_llm(ticker, candidates)

        final: dict[str, float | None] = {}
        decisions: dict[str, Any] = {}

        for field in FIELDS:
            rv = rule_res.get(field)
            lv = llm_res.get(field, {}).get("value")
            conf = llm_res.get(field, {}).get("confidence", 0.0)
            decision = decide_value(field=field, rule_val=rv, llm_val=lv, llm_confidence=conf)
            final[field] = decision["value"]
            decisions[field] = decision

            status = f"{decision['value']:,.0f}" if decision["value"] is not None else "NOT FOUND"
            print(f"    {field}: {status} [{decision['source']} | {decision['reason']}]")

        extracted[ticker] = final
        debug[ticker] = {
            "rule": rule_res,
            "llm": llm_res,
            "decisions": decisions,
            "candidates": candidates,
        }

    return extracted, debug


if __name__ == "__main__":
    extract_all_hybrid()
