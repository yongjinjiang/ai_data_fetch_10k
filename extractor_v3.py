"""
Extractor v3: table-centric chunking with soft-rule LLM resolver.

Pipeline:
  1. Rule baseline  – run v2 extractor for each filing
  2. Table chunks   – parse tables with title/header metadata (table_chunker)
  3. LLM resolve    – send relevant chunks to LLM with soft-rule instructions
  4. Arbitrate      – prefer evidence-backed high-confidence LLM over rule;
                      validator guards sanity and proximity

Emits rich debug info analogous to the hybrid extractor.
"""

from __future__ import annotations

import os
from typing import Any

from config import COMPANIES, DATA_DIR
from extractor_v2 import extract_filing_v2
from table_chunker import extract_tables_for_ticker
from llm_resolver_table import resolve_fields_with_llm_table
from validator import decide_value, is_sane_value
from schema_adapter import from_v3_debug

FIELDS = ["total_revenue", "net_income", "total_assets", "net_cash_from_operating_activities"]


# ---------------------------------------------------------------------------
# Extended arbitration for v3
# ---------------------------------------------------------------------------

def _decide_v3(
    field: str,
    rule_val: float | None,
    llm_res: dict[str, Any],
) -> dict[str, Any]:
    """
    Arbitration policy (extends validator.decide_value):

    Evidence bonus: when LLM supplies table_id + row_label the result is
    considered "evidence-backed", relaxing the proximity requirement for
    medium-confidence LLM picks.

    Sane-value override: if the LLM picks a value that is sane but the rule
    value is None, we still accept the LLM result at confidence >= 0.7.
    """
    llm_val = llm_res.get("value")
    conf = llm_res.get("confidence", 0.0)
    evidence_backed = bool(llm_res.get("table_id") is not None and llm_res.get("row_label"))

    # Rule missing but LLM found something good → accept LLM
    if rule_val is None and llm_val is not None and is_sane_value(field, llm_val) and conf >= 0.7:
        return {
            "value": llm_val,
            "source": "llm_table",
            "reason": "rule_missing_llm_sane",
            "evidence_backed": evidence_backed,
        }

    # Delegate to shared validator for the standard policy
    base = decide_value(field=field, rule_val=rule_val, llm_val=llm_val, llm_confidence=conf)

    # Upgrade medium-confidence evidence-backed picks that are sane (even if not close to rule)
    if (
        base["source"] == "rule"
        and base["reason"] == "medium_conf_fallback"
        and evidence_backed
        and is_sane_value(field, llm_val)
        and conf >= 0.70
    ):
        return {
            "value": llm_val,
            "source": "llm_table",
            "reason": "evidence_backed_medium_conf",
            "evidence_backed": True,
        }

    # Tag source for traceability
    if base["source"] == "llm":
        base["source"] = "llm_table"
    base["evidence_backed"] = evidence_backed
    return base


# ---------------------------------------------------------------------------
# Per-ticker extraction
# ---------------------------------------------------------------------------

def extract_filing_v3(ticker: str) -> tuple[dict[str, float | None], dict[str, Any]]:
    """
    Extract fields for a single ticker using the v3 pipeline.

    Returns:
      final   – {field: value}
      debug   – {rule, chunks_count, llm, decisions}
    """
    filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")

    # Stage 1: rule baseline
    rule_res = extract_filing_v2(filepath) if os.path.exists(filepath) else {f: None for f in FIELDS}

    # Stage 2: table chunks
    chunks = extract_tables_for_ticker(ticker, data_dir=DATA_DIR)

    # Stage 3: LLM resolve
    llm_res = resolve_fields_with_llm_table(ticker, chunks)

    # Stage 4: arbitrate
    final: dict[str, float | None] = {}
    decisions: dict[str, Any] = {}

    for field in FIELDS:
        rv = rule_res.get(field)
        decision = _decide_v3(field, rv, llm_res.get(field, {}))
        final[field] = decision["value"]
        decisions[field] = decision

        status = f"{decision['value']:,.0f}" if decision["value"] is not None else "NOT FOUND"
        src = decision["source"]
        reason = decision["reason"]
        print(f"    {field}: {status} [{src} | {reason}]")

    debug: dict[str, Any] = {
        "rule": rule_res,
        "chunks_count": len(chunks),
        "llm": llm_res,
        "decisions": decisions,
    }

    normalized = from_v3_debug(
        ticker=ticker,
        source_path=filepath,
        final_values=final,
        debug=debug,
    )
    debug["normalized"] = normalized.model_dump(mode="json")

    return final, debug


# ---------------------------------------------------------------------------
# All-tickers runner
# ---------------------------------------------------------------------------

def extract_all_v3() -> tuple[dict[str, dict[str, float | None]], dict[str, Any]]:
    """
    Extract all companies with the v3 pipeline.

    Returns:
      extracted – {ticker: {field: value}}
      debug     – {ticker: debug_dict}
    """
    extracted: dict[str, dict[str, float | None]] = {}
    debug_all: dict[str, Any] = {}

    for ticker in COMPANIES:
        filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
        if not os.path.exists(filepath):
            print(f"  [{ticker}] No file found, skipping.")
            extracted[ticker] = {f: None for f in FIELDS}
            debug_all[ticker] = {
                "error": "file_missing",
                "rule": {f: None for f in FIELDS},
                "chunks_count": 0,
                "llm": {f: {"value": None, "confidence": 0.0, "used_llm": False} for f in FIELDS},
                "decisions": {f: {"value": None, "source": "none", "reason": "file_missing"} for f in FIELDS},
            }
            continue

        print(f"  [{ticker}] Extracting (v3)...")
        final, debug = extract_filing_v3(ticker)
        extracted[ticker] = final
        debug_all[ticker] = debug

    return extracted, debug_all


if __name__ == "__main__":
    extract_all_v3()
