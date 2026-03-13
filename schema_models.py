"""Pydantic models for the common normalized extraction schema.

Contract-first schema used by all source parsers (HTML/PDF).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceInfo(BaseModel):
    type: Literal["html", "pdf"]
    path: str
    filename: str
    mime_type: str
    ingested_at: datetime


class DocumentInfo(BaseModel):
    company: str | None = None
    ticker: str | None = None
    form_type: str | None = None
    fiscal_year: int | None = None
    period_end_date: str | None = None
    filing_date: str | None = None
    title: str | None = None
    language: str | None = None


class Section(BaseModel):
    id: str
    title: str
    level: int = 1
    text: str = ""
    page_start: int | None = None
    page_end: int | None = None
    char_count: int = 0


class Table(BaseModel):
    id: str
    title: str | None = None
    page: int | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    raw_html: str | None = None
    raw_text: str | None = None


class KeyValue(BaseModel):
    key: str
    value: str
    row_label: str | None = None
    value_type: Literal["string", "number", "date", "percent", "currency", "unknown"] = "unknown"
    unit: str | None = None
    context: str | None = None
    section_id: str | None = None
    table_id: str | None = None
    page: int | None = None


class ConfidenceBreakdown(BaseModel):
    overall: float = 0.0
    sections: float = 0.0
    tables: float = 0.0
    key_values: float = 0.0

    @field_validator("overall", "sections", "tables", "key_values")
    @classmethod
    def _clamp_0_1(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class QualityInfo(BaseModel):
    is_digital_pdf: bool | None = None
    text_coverage: float = 0.0
    parse_warnings: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    confidence: ConfidenceBreakdown = Field(default_factory=ConfidenceBreakdown)

    @field_validator("text_coverage")
    @classmethod
    def _clamp_coverage(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class ParserInfo(BaseModel):
    name: str
    version: str


class ProvenanceInfo(BaseModel):
    parser: ParserInfo
    resolver_input_ready: bool = True


class NormalizedContent(BaseModel):
    sections: list[Section] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    key_values: list[KeyValue] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    schema_version: str = "1.0"
    source: SourceInfo
    document: DocumentInfo = Field(default_factory=DocumentInfo)
    content: NormalizedContent = Field(default_factory=NormalizedContent)
    quality: QualityInfo = Field(default_factory=QualityInfo)
    provenance: ProvenanceInfo


HIGH_CONFIDENCE_THRESHOLD = 0.70
VERY_HIGH_CONFIDENCE_THRESHOLD = 0.85
