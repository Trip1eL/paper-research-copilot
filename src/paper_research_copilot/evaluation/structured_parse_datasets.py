"""Versioned dataset contract for structured PDF parsing benchmarks."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader

from paper_research_copilot.domain.structured_parse import (
    StructuredBlockType,
    StructuredParseMethod,
)

StructuredParseCategory = Literal[
    "normal_text",
    "two_column_text",
    "garbled_text",
    "mixed_text_and_garbled_figure",
    "formula_dense",
    "native_table_simple",
    "native_table_multicolumn",
    "native_table_complex",
    "short_visual_page",
    "image_only",
    "scanned_table",
]
REQUIRED_STRUCTURED_CATEGORIES: frozenset[StructuredParseCategory] = frozenset(
    {
        "normal_text",
        "two_column_text",
        "garbled_text",
        "mixed_text_and_garbled_figure",
        "formula_dense",
        "native_table_simple",
        "native_table_multicolumn",
        "native_table_complex",
        "short_visual_page",
        "image_only",
        "scanned_table",
    }
)


class StructuredTableQuestion(BaseModel):
    """A cell relationship that must survive table structure extraction."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=5)
    row_label: str = Field(min_length=1)
    column_headers: tuple[str, ...] = Field(min_length=1)
    expected_answer: str = Field(min_length=1)


class StructuredParseBenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^SPB-[0-9]{3}$")
    source_id: str = Field(min_length=3)
    source_revision: str = Field(min_length=1)
    synthetic: bool = False
    pdf_path: str = Field(min_length=5)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(ge=1)
    category: StructuredParseCategory
    method: StructuredParseMethod
    expected_contains: tuple[str, ...] = Field(min_length=1)
    required_block_types: tuple[StructuredBlockType, ...] = Field(min_length=1)
    table_questions: tuple[StructuredTableQuestion, ...] = ()
    notes: str = Field(min_length=5)

    @model_validator(mode="after")
    def validate_case_contract(self) -> "StructuredParseBenchmarkCase":
        normalized = [value.strip().casefold() for value in self.expected_contains]
        if any(not value for value in normalized):
            raise ValueError("Structured parse text anchors must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Structured parse text anchors must be unique")
        if "table" in self.required_block_types and not self.table_questions:
            raise ValueError("Cases requiring a table block must include table questions")
        if self.category in {"image_only", "scanned_table"} and self.method != "ocr":
            raise ValueError("Image-only structured parse cases must force OCR")
        return self


def load_structured_parse_benchmark(
    path: Path,
    *,
    project_root: Path,
    required_categories: frozenset[StructuredParseCategory] = REQUIRED_STRUCTURED_CATEGORIES,
) -> tuple[StructuredParseBenchmarkCase, ...]:
    cases = tuple(
        StructuredParseBenchmarkCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Structured parse benchmark dataset is empty")
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Structured parse benchmark contains duplicate case IDs")
    missing_categories = required_categories - {case.category for case in cases}
    if missing_categories:
        raise ValueError(
            f"Structured parse benchmark is missing categories: {sorted(missing_categories)}"
        )

    root = project_root.expanduser().resolve()
    verified_hashes: dict[Path, str] = {}
    page_counts: dict[Path, int] = {}
    for case in cases:
        relative_path = Path(case.pdf_path)
        if relative_path.is_absolute():
            raise ValueError(f"Structured parse PDF path must be relative: {case.case_id}")
        pdf_path = (root / relative_path).resolve()
        if not pdf_path.is_relative_to(root):
            raise ValueError(f"Structured parse PDF path escapes project root: {case.case_id}")
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Structured parse PDF does not exist: {case.case_id}")
        actual_hash = verified_hashes.setdefault(pdf_path, _sha256(pdf_path))
        if actual_hash != case.pdf_sha256:
            raise ValueError(f"Structured parse PDF SHA-256 mismatch: {case.case_id}")
        page_count = page_counts.setdefault(pdf_path, len(PdfReader(pdf_path).pages))
        if case.page_number > page_count:
            raise ValueError(f"Structured parse page is out of range: {case.case_id}")
    return cases


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
