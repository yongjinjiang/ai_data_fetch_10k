"""
Extractor v2: Improved rule-based extraction with fixes from error analysis.

Improvements over v1:
1. Skip cells that only contain "$" or currency symbols
2. Added "sales to customers" keyword for JNJ-style filings
3. Added "total revenues and other income" for XOM-style filings
4. Added "total net revenue" for JPM-style (bank) filings
5. Stricter keyword ordering: prefer most specific patterns first
6. Better handling of multi-column tables (prefer first numeric column = most recent year)
7. Suppress XML parsing warnings
"""

import re
import os
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from bs4 import FeatureNotFound
from config import DATA_DIR, COMPANIES

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Keywords ordered from most specific to least specific.
# The extractor tries each pattern and returns the first match.
FIELD_KEYWORDS_V2 = {
    "total_revenue": [
        # Exact "total" prefixed revenue labels (most reliable)
        # Exact "total" prefixed revenue labels (most reliable)
        r"^total\s+net\s+sales$",
        r"^total\s+net\s+revenues?$",
        r"^total\s+revenues?\s+and\s+other\s+income$",
        r"^total\s+revenues?$",
        r"^total\s+revenue$",
        # Bank-specific
        r"^total\s+net\s+revenue$",
        # Company-specific labels
        r"^sales\s+to\s+customers$",
        # Less specific (matched after "total" variants)
        r"^net\s+sales$",
        r"^net\s+revenues?$",
    ],
    "net_income": [
        r"^net\s+income$",
        r"^net\s+earnings$",
        r"^net\s+earnings\s+from\s+continuing\s+operations$",
        r"^net\s+income\s+\(loss\)$",
        r"^net\s+income\s*\(loss\)\s+attributable\s+to",
    ],
    "total_assets": [
        r"^total\s+assets$",
    ],
    "net_cash_from_operating_activities": [
        r"^net\s+cash\s+provided\s+by\s+operating\s+activities$",
        r"^net\s+cash\s+from\s+operating\s+activities$",
        r"^cash\s+provided\s+by\s+operating\s+activities$",
        r"^cash\s+generated\s+from\s+operations$",
        r"^net\s+cash\s+provided\s+by\s+operating\s+operations$",
    ],
}


def parse_number_v2(text: str) -> float | None:
    """Parse a number from text, returning None for non-numeric content."""
    if not text:
        return None
    text = text.strip()

    # Skip cells that are just symbols
    if text in ("$", ")", "(", "%", "—", "–", "-", "", "\xa0"):
        return None

    # Handle parentheses as negative
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    # Remove currency symbols, commas, spaces
    text = text.replace("$", "").replace(",", "").replace(" ", "").replace("\xa0", "")

    # Skip percentage values
    if text.endswith("%"):
        return None

    # Skip empty after cleaning
    if not text or text in ("—", "–", "-"):
        return 0.0

    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


def extract_from_tables_v2(soup: BeautifulSoup, field: str) -> float | None:
    """
    Improved table extraction:
    - Tries patterns in order (most specific first)
    - Skips cells that only contain "$" or empty
    - Returns first valid large number found
    """
    keywords = FIELD_KEYWORDS_V2.get(field, [])
    tables = soup.find_all("table")

    for pattern in keywords:
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue

                # Build label from first cell(s) that contain text
                label_text = cells[0].get_text(strip=True)
                # Some filings split the label across multiple cells; handle first cell only
                label_clean = re.sub(r'\s+', ' ', label_text).strip().lower()

                if re.search(pattern, label_clean, re.IGNORECASE):
                    # Try to extract number from subsequent cells
                    for cell in cells[1:]:
                        num = parse_number_v2(cell.get_text(strip=True))
                        if num is not None and abs(num) > 1:
                            # Sanity check: skip per-share values (too small)
                            if abs(num) < 50 and field != "total_assets":
                                continue
                            return num
        # If a specific pattern found nothing, try the next pattern
    return None


def extract_filing_v2(filepath: str) -> dict:
    """Extract all target fields from a single 10-K filing using v2 logic."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    # Prefer lxml when available, but keep extraction running with stdlib parser.
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")
    results = {}
    for field in FIELD_KEYWORDS_V2:
        results[field] = extract_from_tables_v2(soup, field)
    return results


def extract_all_v2() -> dict:
    """Extract data from all downloaded filings using v2 extractor."""
    all_results = {}
    for ticker in COMPANIES:
        filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
        if not os.path.exists(filepath):
            print(f"  [{ticker}] No file found, skipping.")
            all_results[ticker] = {f: None for f in FIELD_KEYWORDS_V2}
            continue

        print(f"  [{ticker}] Extracting (v2)...")
        results = extract_filing_v2(filepath)
        all_results[ticker] = results
        for field, val in results.items():
            status = f"{val:,.0f}" if val is not None else "NOT FOUND"
            print(f"    {field}: {status}")

    return all_results


if __name__ == "__main__":
    extract_all_v2()
