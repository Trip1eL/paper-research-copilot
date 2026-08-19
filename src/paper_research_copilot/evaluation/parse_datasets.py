"""Versioned dataset contract for PDF parsing benchmarks."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pypdf import PdfReader

ParseCategory = Literal[
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
]

CORE_PARSE_CATEGORIES: frozenset[ParseCategory] = frozenset(
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
    }
)


class ParseTableQuestion(BaseModel):
    """A deterministic table anchor that later parsers must preserve."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=5)
    expected_answer: str = Field(min_length=1)
    required_context: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_required_context(self) -> "ParseTableQuestion":
        normalized = [value.strip().casefold() for value in self.required_context]
        if any(not value for value in normalized):
            raise ValueError("Table question context anchors must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Table question context anchors must be unique")
        return self


class ParseBenchmarkCase(BaseModel):
    """One visually reviewed PDF page with immutable source identity."""

    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^PB-[0-9]{3}$")
    paper_id: str = Field(pattern=r"^arxiv:[0-9]{4}\.[0-9]{4,5}$")
    arxiv_version: str = Field(pattern=r"^[0-9]{4}\.[0-9]{4,5}v[0-9]+$")
    pdf_path: str = Field(min_length=5)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(ge=1)
    category: ParseCategory
    visual_text_present: bool
    expected_text_layer: bool
    expected_contains: tuple[str, ...] = ()
    table_questions: tuple[ParseTableQuestion, ...] = ()
    notes: str = Field(min_length=5)

    @model_validator(mode="after")
    def validate_case_contract(self) -> "ParseBenchmarkCase":
        anchors = [value.strip().casefold() for value in self.expected_contains]
        if any(not value for value in anchors):
            raise ValueError("Expected text anchors must not be empty")
        if len(set(anchors)) != len(anchors):
            raise ValueError("Expected text anchors must be unique")
        if self.category.startswith("native_table_") and not self.table_questions:
            raise ValueError("Native table cases require at least one table question")
        if self.category == "image_only" and self.expected_text_layer:
            raise ValueError("An image_only case cannot expect an embedded text layer")
        if self.expected_contains and not self.expected_text_layer:
            raise ValueError("Text anchors require an expected embedded text layer")
        return self


def load_parse_benchmark(
    path: Path,
    *,
    project_root: Path,
    required_categories: frozenset[ParseCategory] = CORE_PARSE_CATEGORIES,
) -> tuple[ParseBenchmarkCase, ...]:
    """Load a benchmark and validate every source PDF against its frozen identity."""

    cases = tuple(
        ParseBenchmarkCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Parse benchmark dataset is empty")

    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Parse benchmark dataset contains duplicate case IDs")

    missing_categories = required_categories - {case.category for case in cases}
    if missing_categories:
        raise ValueError(
            f"Parse benchmark dataset is missing required categories: {sorted(missing_categories)}"
        )

    root = project_root.expanduser().resolve()
    page_counts: dict[Path, int] = {}
    verified_hashes: dict[Path, str] = {}
    for case in cases:
        relative_path = Path(case.pdf_path)
        if relative_path.is_absolute():
            raise ValueError(f"Parse benchmark PDF path must be relative: {case.case_id}")
        pdf_path = (root / relative_path).resolve()
        if not pdf_path.is_relative_to(root):
            raise ValueError(f"Parse benchmark PDF path escapes project root: {case.case_id}")
        if pdf_path.suffix.lower() != ".pdf" or not pdf_path.is_file():
            raise ValueError(f"Parse benchmark PDF does not exist: {case.case_id}:{case.pdf_path}")

        actual_sha256 = verified_hashes.setdefault(pdf_path, _sha256(pdf_path))
        if actual_sha256 != case.pdf_sha256:
            raise ValueError(f"Parse benchmark PDF SHA-256 mismatch: {case.case_id}")

        if pdf_path not in page_counts:
            page_counts[pdf_path] = len(PdfReader(pdf_path).pages)
        if case.page_number > page_counts[pdf_path]:
            raise ValueError(
                "Parse benchmark page is out of range: "
                f"{case.case_id}:p{case.page_number}>{page_counts[pdf_path]}"
            )
    return cases


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
