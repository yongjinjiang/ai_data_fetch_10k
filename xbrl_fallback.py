"""Inline XBRL fallback helpers for targeted hard cases (v4.3)."""

from __future__ import annotations

import re
from typing import Iterable


FIELD_TAGS = {
    "total_revenue": [
        "us-gaap:Revenues",
        "us-gaap:SalesRevenueNet",
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    ],
    "net_income": [
        "us-gaap:NetIncomeLoss",
    ],
    "total_assets": [
        "us-gaap:Assets",
    ],
    "net_cash_from_operating_activities": [
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
}


def _parse_number(text: str) -> float | None:
    t = (text or "").strip()
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    t = t.replace(",", "").replace("$", "").replace("\xa0", " ").strip()
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _apply_scale(v: float, scale: str | None) -> float:
    if scale is None:
        return v
    try:
        s = int(scale)
        return v * (10 ** s)
    except Exception:
        return v


def _iter_ix_values(html: str, tag_names: Iterable[str]) -> list[float]:
    vals: list[float] = []
    names = "|".join(re.escape(n) for n in tag_names)

    # Match inline XBRL nonFraction tags with possible attributes ordering.
    pattern = re.compile(
        rf"<ix:nonfraction[^>]*?name=[\"'](?:{names})[\"'][^>]*>(.*?)</ix:nonfraction>",
        re.IGNORECASE | re.DOTALL,
    )

    for m in pattern.finditer(html):
        full_tag = m.group(0)
        raw = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        v = _parse_number(raw)
        if v is None:
            continue

        scale_m = re.search(r"\bscale=[\"'](-?\d+)[\"']", full_tag, re.IGNORECASE)
        scale = scale_m.group(1) if scale_m else None
        v = _apply_scale(v, scale)

        # Inline XBRL may encode sign separately.
        sign_m = re.search(r"\bsign=[\"']-?[\"']", full_tag, re.IGNORECASE)
        if sign_m and "-" in sign_m.group(0):
            v = -abs(v)

        # Normalize to millions USD if number appears to be raw dollars.
        if abs(v) >= 10_000_000:
            v = v / 1_000_000

        vals.append(v)

    return vals


def get_xbrl_best_value(filepath: str, field: str) -> float | None:
    tags = FIELD_TAGS.get(field, [])
    if not tags:
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
    except Exception:
        return None

    vals = _iter_ix_values(html, tags)
    if not vals:
        return None

    # Heuristic: choose largest absolute magnitude (often current-year consolidated value).
    vals = [v for v in vals if abs(v) > 1]
    if not vals:
        return None
    return max(vals, key=lambda x: abs(x))
