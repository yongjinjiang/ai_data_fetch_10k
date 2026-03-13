"""Input router: dispatch HTML/PDF sources to normalized schema producers."""

from __future__ import annotations

from typing import Any

from pdf_parser import parse_pdf_to_normalized
from schema_adapter import from_v3_debug
from schema_models import NormalizedDocument


class UnsupportedInputError(ValueError):
    pass


def route_to_normalized(
    *,
    source_path: str,
    ticker: str,
    final_values: dict[str, float | None] | None = None,
    debug: dict[str, Any] | None = None,
) -> NormalizedDocument:
    """Route source file to the appropriate normalized-schema producer.

    - .htm/.html: uses existing v3 adapter (requires final_values + debug)
    - .pdf: uses digital-PDF parser
    """
    p = source_path.lower()

    if p.endswith(".pdf"):
        return parse_pdf_to_normalized(source_path=source_path, ticker=ticker)

    if p.endswith(".htm") or p.endswith(".html"):
        if final_values is None or debug is None:
            raise UnsupportedInputError("HTML routing requires final_values and debug for v3 adapter")
        return from_v3_debug(
            ticker=ticker,
            source_path=source_path,
            final_values=final_values,
            debug=debug,
        )

    raise UnsupportedInputError(f"Unsupported input type for: {source_path}")
