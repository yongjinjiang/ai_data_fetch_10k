"""Validation helpers for normalized schema objects."""

from __future__ import annotations

from datetime import date

from schema_models import NormalizedDocument


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return True
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_normalized_document(doc: NormalizedDocument) -> NormalizedDocument:
    """Apply project-level validation rules and annotate validation_errors.

    Mutates and returns the same document instance for convenience.
    """
    errors = doc.quality.validation_errors

    if doc.source.type not in {"html", "pdf"}:
        errors.append("INVALID_SOURCE_TYPE")

    if not _is_iso_date(doc.document.period_end_date):
        errors.append("INVALID_PERIOD_END_DATE")

    if not _is_iso_date(doc.document.filing_date):
        errors.append("INVALID_FILING_DATE")

    if doc.source.type == "pdf" and doc.quality.is_digital_pdf is False:
        errors.append("UNSUPPORTED_SCANNED_OR_IMAGE_PDF")
        doc.provenance.resolver_input_ready = False

    if doc.quality.text_coverage < 0.05:
        errors.append("LOW_TEXT_COVERAGE")

    return doc
