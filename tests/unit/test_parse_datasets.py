import hashlib
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from paper_research_copilot.evaluation.parse_datasets import (
    CORE_PARSE_CATEGORIES,
    ParseBenchmarkCase,
    load_parse_benchmark,
)


def _write_pdf(path: Path, *, page_count: int = 1) -> str:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as file:
        writer.write(file)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(pdf_sha256: str, **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "case_id": "PB-001",
        "paper_id": "arxiv:0000.00000",
        "arxiv_version": "0000.00000v1",
        "pdf_path": "paper.pdf",
        "pdf_sha256": pdf_sha256,
        "page_number": 1,
        "category": "normal_text",
        "visual_text_present": True,
        "expected_text_layer": True,
        "expected_contains": [],
        "table_questions": [],
        "notes": "Unit test fixture.",
    }
    record.update(overrides)
    return record


def _write_dataset(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_load_parse_benchmark_validates_local_pdf(tmp_path: Path) -> None:
    pdf_sha256 = _write_pdf(tmp_path / "paper.pdf")
    dataset = tmp_path / "parse.jsonl"
    _write_dataset(dataset, [_record(pdf_sha256)])

    cases = load_parse_benchmark(
        dataset,
        project_root=tmp_path,
        required_categories=frozenset(),
    )

    assert len(cases) == 1
    assert cases[0].pdf_sha256 == pdf_sha256


def test_load_parse_benchmark_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    pdf_sha256 = _write_pdf(tmp_path / "paper.pdf")
    dataset = tmp_path / "parse.jsonl"
    _write_dataset(dataset, [_record(pdf_sha256), _record(pdf_sha256)])

    with pytest.raises(ValueError, match="duplicate case IDs"):
        load_parse_benchmark(
            dataset,
            project_root=tmp_path,
            required_categories=frozenset(),
        )


def test_load_parse_benchmark_rejects_sha_mismatch(tmp_path: Path) -> None:
    _write_pdf(tmp_path / "paper.pdf")
    dataset = tmp_path / "parse.jsonl"
    _write_dataset(dataset, [_record("0" * 64)])

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_parse_benchmark(
            dataset,
            project_root=tmp_path,
            required_categories=frozenset(),
        )


def test_load_parse_benchmark_rejects_path_traversal(tmp_path: Path) -> None:
    dataset = tmp_path / "parse.jsonl"
    _write_dataset(dataset, [_record("0" * 64, pdf_path="../outside.pdf")])

    with pytest.raises(ValueError, match="escapes project root"):
        load_parse_benchmark(
            dataset,
            project_root=tmp_path,
            required_categories=frozenset(),
        )


def test_load_parse_benchmark_rejects_out_of_range_page(tmp_path: Path) -> None:
    pdf_sha256 = _write_pdf(tmp_path / "paper.pdf")
    dataset = tmp_path / "parse.jsonl"
    _write_dataset(dataset, [_record(pdf_sha256, page_number=2)])

    with pytest.raises(ValueError, match="out of range"):
        load_parse_benchmark(
            dataset,
            project_root=tmp_path,
            required_categories=frozenset(),
        )


def test_native_table_case_requires_table_question() -> None:
    with pytest.raises(ValueError, match="require at least one table question"):
        ParseBenchmarkCase.model_validate(_record("0" * 64, category="native_table_simple"))


def test_versioned_parse_dataset_covers_frozen_categories() -> None:
    project_root = Path(__file__).parents[2]
    records = [
        ParseBenchmarkCase.model_validate(json.loads(line))
        for line in (project_root / "evals" / "datasets" / "parse_benchmark_v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(records) == 10
    assert {record.category for record in records} == CORE_PARSE_CATEGORIES
    assert len({record.case_id for record in records}) == len(records)
    assert sum(bool(record.table_questions) for record in records) == 3
