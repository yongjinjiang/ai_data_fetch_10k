"""
Extractor v1: Rule-based extraction of financial data from 10-K HTML filings.
Uses BeautifulSoup + regex to find values in financial statement tables.
"""

import re
import os
from bs4 import BeautifulSoup
from bs4 import FeatureNotFound
from config import DATA_DIR, COMPANIES

# Keywords to match for each field (intentionally limited in v1 for <100% accuracy)
FIELD_KEYWORDS = {
    "total_revenue": [
        r"total\s+net\s+revenues?",
        r"net\s+revenues?",
        r"total\s+revenues?",
        r"revenues?",
        r"net\s+sales",
    ],
    "net_income": [
        r"net\s+income\s*$",
        r"net\s+income\s*\(",
        r"net\s+earnings",
    ],
    "total_assets": [
        r"total\s+assets",
    ],
    "net_cash_from_operating_activities": [
        r"net\s+cash\s+provided\s+by\s+operating\s+activities",
        r"net\s+cash\s+from\s+operating\s+activities",
        r"cash\s+provided\s+by\s+operating\s+activities",
        r"cash\s+generated\s+from\s+operations",
    ],
}


def parse_number(text: str) -> float | None:
    """Parse a number from text like '394,328' or '(1,234)' or '$12.5'."""
    if not text:
        return None
    text = text.strip()
    # Handle parentheses as negative
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    # Remove $ and whitespace
    text = text.replace("$", "").replace(",", "").replace(" ", "").replace("\xa0", "")
    # Handle em-dash or en-dash as zero
    if text in ("—", "–", "-", ""):
        return 0.0
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


def extract_from_tables(soup: BeautifulSoup, field: str) -> float | None:
    """Search all HTML tables for a row matching field keywords, return the first number found."""
    keywords = FIELD_KEYWORDS.get(field, [])
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            # Check if the first cell text matches any keyword
            label_text = cells[0].get_text(strip=True).lower()
            for pattern in keywords:
                if re.search(pattern, label_text, re.IGNORECASE):
                    # Try to extract number from subsequent cells
                    for cell in cells[1:]:
                        num = parse_number(cell.get_text(strip=True))
                        if num is not None and num != 0:
                            return num
    return None


def extract_filing(filepath: str) -> dict:
    """Extract all target fields from a single 10-K filing."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    # Prefer lxml when available, but keep extraction running with stdlib parser.
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")
    results = {}
    for field in FIELD_KEYWORDS:
        results[field] = extract_from_tables(soup, field)
    return results


def extract_all() -> dict:
    """Extract data from all downloaded filings. Returns {ticker: {field: value}}."""
    all_results = {}
    for ticker in COMPANIES:
        filepath = os.path.join(DATA_DIR, f"{ticker}_10k.htm")
        if not os.path.exists(filepath):
            print(f"  [{ticker}] No file found, skipping.")
            all_results[ticker] = {f: None for f in FIELD_KEYWORDS}
            continue

        print(f"  [{ticker}] Extracting...")
        results = extract_filing(filepath)
        all_results[ticker] = results
        for field, val in results.items():
            status = f"{val:,.0f}" if val is not None else "NOT FOUND"
            print(f"    {field}: {status}")

    return all_results


if __name__ == "__main__":
    extract_all()
