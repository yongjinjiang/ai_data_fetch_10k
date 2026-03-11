"""
Table-centric chunker for 10-K HTML filings.

Extracts tables with rich metadata:
  - table_id: sequential index in document
  - title: nearest preceding heading or caption text
  - header_rows: detected header rows (list of cell text lists)
  - rows: data rows as lists of cell text
  - serialized: plain-text representation for LLM prompts
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Headings and structural tags used to infer table context
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "caption", "p", "div", "span"}

# Minimum columns for a table to be considered data-bearing
_MIN_COLS = 2
# Maximum rows we keep per table chunk (avoids giant tables)
_MAX_ROWS = 60


def _clean(text: str) -> str:
    """Normalise whitespace and strip a text snippet."""
    return re.sub(r"\s+", " ", text or "").strip()


def _is_likely_header_row(cells: list[str]) -> bool:
    """
    Heuristic: a row is a header if it has no numeric cells OR the first
    cell is empty/short and the remaining cells look like year labels.
    """
    if not cells:
        return False
    # All cells non-numeric → likely header
    numeric_count = 0
    for c in cells:
        stripped = c.replace(",", "").replace("$", "").replace("(", "").replace(")", "").strip()
        try:
            float(stripped)
            numeric_count += 1
        except ValueError:
            pass
    if numeric_count == 0:
        return True
    # First cell empty / label-like, rest look like years (4-digit numbers 19xx-20xx)
    if cells and re.match(r"^\d{4}$", cells[0].strip()):
        return False  # actually a data row with year as label
    year_like = sum(1 for c in cells[1:] if re.match(r"^\d{4}$", c.strip()))
    if year_like >= max(1, len(cells) - 1) // 2:
        return True
    return False


def _nearest_heading(element: Any) -> str:
    """
    Walk backwards through siblings and ancestors to find the nearest
    heading-like text that precedes this table.
    """
    candidates: list[str] = []

    # Look at previous siblings in the same parent
    for sibling in element.find_previous_siblings():
        tag = getattr(sibling, "name", None)
        if tag in _HEADING_TAGS or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            txt = _clean(sibling.get_text(" ", strip=True))
            if txt and len(txt) < 300:
                candidates.append(txt)
                if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    break  # strong heading — stop looking
                if len(candidates) >= 3:
                    break

    if candidates:
        return candidates[0]

    # Fallback: check caption child
    cap = element.find("caption")
    if cap:
        return _clean(cap.get_text(" ", strip=True))

    return ""


def extract_tables(html: str) -> list[dict[str, Any]]:
    """
    Parse ``html`` and return a list of table chunk dicts.

    Each dict has:
      table_id     : int
      title        : str  (nearest heading / caption)
      header_rows  : list[list[str]]
      rows         : list[list[str]]   (data rows, excl. headers)
      serialized   : str  (compact text for LLM)
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")

    chunks: list[dict[str, Any]] = []

    for table_id, table in enumerate(soup.find_all("table")):
        rows_raw = table.find_all("tr")
        if not rows_raw:
            continue

        all_rows: list[list[str]] = []
        for tr in rows_raw:
            cells = [_clean(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if cells:
                all_rows.append(cells)

        # Skip tables with too few columns or rows
        max_cols = max((len(r) for r in all_rows), default=0)
        if max_cols < _MIN_COLS or len(all_rows) < 2:
            continue

        # Split header vs data rows
        header_rows: list[list[str]] = []
        data_rows: list[list[str]] = []
        for row in all_rows:
            if not data_rows and _is_likely_header_row(row):
                header_rows.append(row)
            else:
                data_rows.append(row)

        # Trim oversized tables
        data_rows = data_rows[:_MAX_ROWS]

        title = _nearest_heading(table)

        chunk: dict[str, Any] = {
            "table_id": table_id,
            "title": title,
            "header_rows": header_rows,
            "rows": data_rows,
            "serialized": _serialize(table_id, title, header_rows, data_rows),
        }
        chunks.append(chunk)

    return chunks


def _serialize(
    table_id: int,
    title: str,
    header_rows: list[list[str]],
    data_rows: list[list[str]],
) -> str:
    """Produce a compact, readable text block for use in LLM prompts."""
    lines: list[str] = [f"[TABLE {table_id}]"]
    if title:
        lines.append(f"Title: {title}")
    if header_rows:
        for hr in header_rows:
            lines.append("HDR | " + " | ".join(hr))
    for row in data_rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def extract_tables_for_ticker(ticker: str, data_dir: str = "data") -> list[dict[str, Any]]:
    """Load the filing HTML for *ticker* and return table chunks."""
    import os

    filepath = os.path.join(data_dir, f"{ticker}_10k.htm")
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
        html = fh.read()
    return extract_tables(html)
