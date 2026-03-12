"""
Extractor v4: semantic locator + deterministic reader.

Pipeline:
  1) Rule baseline (v2)
  2) Table chunk extraction
  3) LLM locator predicts table/row/column labels per field (no numeric output)
  4) Python reads numeric value at located cell
  5) Arbitration against rule baseline
"""

from __future__ import annotations

import os
from typing import Any

from config import COMPANIES, DATA_DIR
from extractor_v2 import extract_filing_v2
from llm_locator_table import locate_fields_with_llm_table
from table_chunker import extract_tables_for_ticker
from table_value_reader import read_value_from_chunks
from validator import decide_value, is_sane_value

FIELDS = ["total_revenue", "net_income", "total_assets", "net_cash_from_operating_activities"]


def _decide_v4(field: str, rule_val: float | None, located_val: float | None, conf: float) -> dict[str, Any]:
    # If rule missing and located value seems sane with decent confidence, take locator value
    if rule_val is None and located_val is not None and is_sane_value(field, located_val) and conf >= 0.65:
        return {"value": located_val, "source": "locator_reader", "reason": "rule_missing_locator_sane"}

    base = decide_value(field=field, rule_val=rule_val, llm_val=located_val, llm_confidence=conf)
    if base["source"] == "llm":
        base["source"] = "locator_reader"
    return base


def extract_filing_v4(ticker: str) -> tuple[dict[str, float | None], dict[str, Any]]:
    filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")

    rule_res = extract_filing_v2(filepath) if os.path.exists(filepath) else {f: None for f in FIELDS}
    chunks = extract_tables_for_ticker(ticker, data_dir=DATA_DIR)
    loc = locate_fields_with_llm_table(ticker, chunks)

    final: dict[str, float | None] = {}
    decisions: dict[str, Any] = {}
    reader_debug: dict[str, Any] = {}

    for field in FIELDS:
        l = loc.get(field, {})
        val, dbg = read_value_from_chunks(
            chunks=chunks,
            table_id=l.get("table_id"),
            row_label=l.get("row_label"),
            column_label=l.get("column_label"),
        )
        conf = float(l.get("confidence", 0.0) or 0.0)
        decision = _decide_v4(field, rule_res.get(field), val, conf)

        final[field] = decision["value"]
        decisions[field] = decision
        reader_debug[field] = {"located_value": val, "read_debug": dbg, "locator": l}

        status = f"{decision['value']:,.0f}" if decision["value"] is not None else "NOT FOUND"
        print(f"    {field}: {status} [{decision['source']} | {decision['reason']}]")

    debug = {
        "rule": rule_res,
        "chunks_count": len(chunks),
        "locator": loc,
        "reader": reader_debug,
        "decisions": decisions,
    }
    return final, debug


def extract_all_v4() -> tuple[dict[str, dict[str, float | None]], dict[str, Any]]:
    extracted: dict[str, dict[str, float | None]] = {}
    debug_all: dict[str, Any] = {}

    for ticker in COMPANIES:
        filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
        if not os.path.exists(filepath):
            print(f"  [{ticker}] No file found, skipping.")
            extracted[ticker] = {f: None for f in FIELDS}
            debug_all[ticker] = {"error": "file_missing"}
            continue

        print(f"  [{ticker}] Extracting (v4)...")
        final, dbg = extract_filing_v4(ticker)
        extracted[ticker] = final
        debug_all[ticker] = dbg

    return extracted, debug_all


if __name__ == "__main__":
    extract_all_v4()
