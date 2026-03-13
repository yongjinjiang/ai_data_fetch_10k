"""Digital-PDF parser that emits the common normalized schema."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from schema_models import (
    DocumentInfo,
    NormalizedContent,
    NormalizedDocument,
    ParserInfo,
    ProvenanceInfo,
    QualityInfo,
    Section,
    SourceInfo,
)
from schema_validation import validate_normalized_document


def parse_pdf_to_normalized(*, source_path: str, ticker: str | None = None) -> NormalizedDocument:
    """Parse digital PDF text into normalized schema.

    Note: this parser focuses on structure extraction (metadata + sections).
    Numeric field extraction remains downstream resolver work.
    """
    reader = PdfReader(source_path)
    total_pages = len(reader.pages)

    sections: list[Section] = []
    pages_with_text = 0
    total_chars = 0

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages_with_text += 1
        total_chars += len(text)
        sections.append(
            Section(
                id=f"p{i}",
                title=f"page_{i}",
                level=1,
                text=text,
                page_start=i,
                page_end=i,
                char_count=len(text),
            )
        )

    is_digital = pages_with_text > 0 and total_chars > 200
    coverage = (pages_with_text / total_pages) if total_pages > 0 else 0.0

    doc = NormalizedDocument(
        source=SourceInfo(
            type="pdf",
            path=source_path,
            filename=Path(source_path).name,
            mime_type="application/pdf",
            ingested_at=datetime.utcnow(),
        ),
        document=DocumentInfo(ticker=ticker, form_type="10-K"),
        content=NormalizedContent(sections=sections, tables=[], key_values=[]),
        quality=QualityInfo(
            is_digital_pdf=is_digital,
            text_coverage=coverage,
            parse_warnings=[] if is_digital else ["LOW_OR_NO_EXTRACTABLE_TEXT"],
            validation_errors=[],
            confidence={
                "overall": 0.75 if is_digital else 0.0,
                "sections": 0.9 if is_digital else 0.0,
                "tables": 0.0,
                "key_values": 0.0,
            },
        ),
        provenance=ProvenanceInfo(
            parser=ParserInfo(name="pdf_parser", version="v1"),
            resolver_input_ready=is_digital,
        ),
    )

    return validate_normalized_document(doc)
