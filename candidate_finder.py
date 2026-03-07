"""
Candidate finder for hybrid extraction.
Collects plausible numeric rows from 10-K HTML tables for each target field.
"""

from __future__ import annotations

import os
import re
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

from config import COMPANIES, DATA_DIR

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

FIELD_PATTERNS = {
    "total_revenue": [
        r"total\s+net\s+sales",
        r"total\s+net\s+revenue",
        r"total\s+revenue",
        r"total\s+revenues",
        r"sales\s+to\s+customers",
        r"net\s+sales",
        r"net\s+revenues?",
        r"revenues?",
    ],
    "net_income": [
        r"net\s+income",
        r"net\s+earnings",
        r"income\s+\(loss\)",
    ],
    "total_assets": [
        r"total\s+assets",
    ],
}


def parse_number(text: str) -> float | None:
    """Parse value from a cell string."""
    if not text:
        return None
    txt = text.strip()
    if txt in ("$", "(", ")", "%", "", "—", "–", "-"):
        return None

    neg = False
    if txt.startswith("(") and txt.endswith(")"):
        neg = True
        txt = txt[1:-1]

    txt = txt.replace("$", "").replace(",", "").replace(" ", "").replace("\xa0", "")
    if not txt:
        return None

    if txt.endswith("%"):
        return None

    try:
        val = float(txt)
    except ValueError:
        return None
    return -val if neg else val


def _row_label(cells: list[Any]) -> str:
    label = cells[0].get_text(" ", strip=True) if cells else ""
    return re.sub(r"\s+", " ", label).strip()


def find_candidates_in_html(html: str, max_candidates_per_field: int = 8) -> dict[str, list[dict[str, Any]]]:
    """Find candidate rows by field from all tables in filing HTML."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in FIELD_PATTERNS}

    for table_idx, table in enumerate(soup.find_all("table")):
        for row_idx, row in enumerate(table.find_all("tr")):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            label = _row_label(cells)
            if not label:
                continue
            label_l = label.lower()

            nums: list[float] = []
            for c in cells[1:]:
                n = parse_number(c.get_text(strip=True))
                if n is not None and abs(n) > 1:
                    nums.append(n)

            if not nums:
                continue

            value = nums[0]  # first numeric col generally latest year
            for field, patterns in FIELD_PATTERNS.items():
                if any(re.search(p, label_l, re.IGNORECASE) for p in patterns):
                    out[field].append(
                        {
                            "label": label,
                            "value": value,
                            "table_index": table_idx,
                            "row_index": row_idx,
                        }
                    )

    # Keep top-k by absolute value to reduce prompt size/noise
    for field in out:
        out[field] = sorted(out[field], key=lambda x: abs(x["value"]), reverse=True)[:max_candidates_per_field]
    return out


def find_candidates_for_ticker(ticker: str, max_candidates_per_field: int = 8) -> dict[str, list[dict[str, Any]]]:
    filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
    if not os.path.exists(filepath):
        return {k: [] for k in FIELD_PATTERNS}
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    return find_candidates_in_html(html, max_candidates_per_field=max_candidates_per_field)


def find_candidates_all(max_candidates_per_field: int = 8) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Return {ticker: {field: [candidate rows]}}."""
    result = {}
    for ticker in COMPANIES:
        result[ticker] = find_candidates_for_ticker(ticker, max_candidates_per_field=max_candidates_per_field)
    return result
