"""
Validation and arbitration helpers for hybrid extraction.
"""

from __future__ import annotations

from typing import Any


def is_sane_value(field: str, value: float | None) -> bool:
    """Basic sanity check for extracted financial values (in millions USD)."""
    if value is None:
        return False
    if value <= 0:
        return False

    # Broad but useful ranges in millions USD
    ranges = {
        "total_revenue": (100, 5_000_000),
        "net_income": (1, 1_000_000),
        "total_assets": (100, 20_000_000),
    }
    lo, hi = ranges.get(field, (1, 1_000_000_000))
    return lo <= abs(value) <= hi


def close_to_rule(rule_val: float | None, llm_val: float | None, pct_threshold: float = 20.0) -> bool:
    """Check whether llm value is within threshold of rule value."""
    if rule_val is None or llm_val is None:
        return False
    if rule_val == 0:
        return False
    pct = abs(llm_val - rule_val) / abs(rule_val) * 100
    return pct <= pct_threshold


def decide_value(
    field: str,
    rule_val: float | None,
    llm_val: float | None,
    llm_confidence: float,
) -> dict[str, Any]:
    """
    Arbitration policy:
    - conf >= 0.9: accept LLM if sane else fallback rule
    - 0.6 <= conf < 0.9: accept LLM only if sane and close to rule, else rule
    - conf < 0.6: fallback rule
    """
    if llm_val is None:
        return {"value": rule_val, "source": "rule", "reason": "llm_missing"}

    if llm_confidence >= 0.9:
        if is_sane_value(field, llm_val):
            return {"value": llm_val, "source": "llm", "reason": "high_confidence"}
        return {"value": rule_val, "source": "rule", "reason": "llm_high_conf_but_insane"}

    if 0.6 <= llm_confidence < 0.9:
        if is_sane_value(field, llm_val) and close_to_rule(rule_val, llm_val):
            return {"value": llm_val, "source": "llm", "reason": "medium_conf_validated"}
        return {"value": rule_val, "source": "rule", "reason": "medium_conf_fallback"}

    return {"value": rule_val, "source": "rule", "reason": "low_confidence"}
