"""Adapters from extractor outputs to the common normalized schema."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from schema_models import (
    DocumentInfo,
    KeyValue,
    NormalizedContent,
    NormalizedDocument,
    ParserInfo,
    ProvenanceInfo,
    QualityInfo,
    Section,
    SourceInfo,
    Table,
)
from schema_validation import validate_normalized_document


def _infer_mime(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):
        return "application/pdf"
    if p.endswith(".htm") or p.endswith(".html"):
        return "text/html"
    return "application/octet-stream"


def _infer_source_type(path: str) -> str:
    return "pdf" if path.lower().endswith(".pdf") else "html"


def from_v3_debug(
    *,
    ticker: str,
    source_path: str,
    final_values: dict[str, float | None],
    debug: dict[str, Any],
) -> NormalizedDocument:
    """Build a normalized document from v3 extraction outputs."""
    llm = debug.get("llm", {})

    # Minimal sections placeholder keeps schema stable even when parser is table-centric.
    sections = [
        Section(
            id="s0",
            title="financial_tables",
            level=1,
            text="Extracted from table-centric pipeline",
            char_count=len("Extracted from table-centric pipeline"),
        )
    ]

    tables: list[Table] = []
    key_values: list[KeyValue] = []

    for field, value in final_values.items():
        llm_meta = llm.get(field, {}) if isinstance(llm, dict) else {}
        table_id = llm_meta.get("table_id")
        row_label = llm_meta.get("row_label")

        key_values.append(
            KeyValue(
                key=field,
                value="" if value is None else str(value),
                row_label=row_label,
                value_type="number" if value is not None else "unknown",
                unit=llm_meta.get("unit") or "millions USD",
                context=llm_meta.get("column_label"),
                section_id="s0",
                table_id=(None if table_id is None else f"table_{table_id}"),
            )
        )

        if table_id is not None:
            tables.append(
                Table(
                    id=f"table_{table_id}",
                    title=llm_meta.get("source_label") or row_label,
                    page=None,
                    headers=[llm_meta.get("column_label")] if llm_meta.get("column_label") else [],
                    rows=[[row_label or "", "" if value is None else str(value)]],
                    raw_text=None,
                )
            )

    source = SourceInfo(
        type=_infer_source_type(source_path),
        path=source_path,
        filename=Path(source_path).name,
        mime_type=_infer_mime(source_path),
        ingested_at=datetime.utcnow(),
    )

    confidence_values = [
        float((llm.get(f, {}) or {}).get("confidence", 0.0))
        for f in final_values.keys()
    ]
    overall = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0

    doc = NormalizedDocument(
        source=source,
        document=DocumentInfo(ticker=ticker, form_type="10-K"),
        content=NormalizedContent(sections=sections, tables=tables, key_values=key_values),
        quality=QualityInfo(
            is_digital_pdf=(source.type != "pdf") or True,
            text_coverage=1.0 if key_values else 0.0,
            parse_warnings=[],
            validation_errors=[],
            confidence={
                "overall": overall,
                "sections": 0.9,
                "tables": overall,
                "key_values": overall,
            },
        ),
        provenance=ProvenanceInfo(
            parser=ParserInfo(name="extractor_v3", version="v3"),
            resolver_input_ready=True,
        ),
    )

    return validate_normalized_document(doc)
