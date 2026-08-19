from pathlib import Path

from paper_research_copilot.domain import PageTextExtraction, ParserName
from paper_research_copilot.evaluation.parse_datasets import ParseBenchmarkCase
from paper_research_copilot.evaluation.parse_shadow import (
    ShadowParseConfig,
    build_shadow_parse_report,
    run_shadow_parse_benchmark,
    write_shadow_parse_artifacts,
)
from paper_research_copilot.ingestion import FastParserRouter


class _FakeExtractor:
    def __init__(
        self,
        parser_name: ParserName,
        pages: tuple[PageTextExtraction, ...],
    ) -> None:
        self._parser_name = parser_name
        self._pages = pages
        self.calls = 0

    @property
    def parser_name(self) -> ParserName:
        return self._parser_name

    @property
    def parser_version(self) -> str:
        return "test"

    def extract(self, path: Path) -> tuple[PageTextExtraction, ...]:
        self.calls += 1
        return self._pages


def _page(page_number: int, text: str, parser_name: ParserName) -> PageTextExtraction:
    return PageTextExtraction(
        page_number=page_number,
        text=text,
        parser_name=parser_name,
        parser_version="test",
        latency_ms=1,
        width=612,
        height=792,
        image_count=0,
    )


def _case(case_id: str, page_number: int, category: str, anchor: str) -> ParseBenchmarkCase:
    return ParseBenchmarkCase.model_validate(
        {
            "case_id": case_id,
            "paper_id": "arxiv:0000.00000",
            "arxiv_version": "0000.00000v1",
            "pdf_path": "paper.pdf",
            "pdf_sha256": "0" * 64,
            "page_number": page_number,
            "category": category,
            "visual_text_present": True,
            "expected_text_layer": True,
            "expected_contains": [anchor],
            "notes": "Unit test fixture.",
        }
    )


def test_shadow_benchmark_caches_documents_and_reports_recovery(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-shadow-test")
    clean = "clean anchor " * 100
    recovered = "recovered anchor " * 100
    primary = _FakeExtractor(
        "pypdf",
        (
            _page(1, clean, "pypdf"),
            _page(2, ("bad " * 100) + ("\x03" * 100), "pypdf"),
        ),
    )
    secondary = _FakeExtractor(
        "pymupdf",
        (
            _page(1, clean, "pymupdf"),
            _page(2, recovered, "pymupdf"),
        ),
    )
    router = FastParserRouter(primary, secondary)
    cases = (
        _case("PB-001", 1, "normal_text", "clean anchor"),
        _case("PB-002", 2, "garbled_text", "recovered anchor"),
    )

    results = run_shadow_parse_benchmark(cases, project_root=tmp_path, router=router)
    report = build_shadow_parse_report(
        results,
        ShadowParseConfig(
            baseline_id="shadow_test",
            evaluated_on="2026-08-19",
            dataset_path="test.jsonl",
            dataset_sha256="0" * 64,
            primary_parser="pypdf==test",
            secondary_parser="pymupdf==test",
        ),
    )

    assert primary.calls == secondary.calls == 1
    assert report.primary_issue_detection_rate == 1
    assert report.known_issue_recovery_rate == 1
    assert report.clean_primary_retention_rate == 1
    assert report.selected_text_anchor_pass_rate == 1


def test_shadow_report_writes_json_and_markdown(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-shadow-test")
    clean = "clean anchor " * 100
    primary = _FakeExtractor(
        "pypdf",
        (_page(1, clean, "pypdf"), _page(2, clean, "pypdf")),
    )
    secondary = _FakeExtractor(
        "pymupdf",
        (_page(1, clean, "pymupdf"), _page(2, clean, "pymupdf")),
    )
    router = FastParserRouter(primary, secondary)
    cases = (
        _case("PB-001", 1, "normal_text", "clean anchor"),
        _case("PB-002", 2, "garbled_text", "clean anchor"),
    )
    results = run_shadow_parse_benchmark(cases, project_root=tmp_path, router=router)
    report = build_shadow_parse_report(
        results,
        ShadowParseConfig(
            baseline_id="shadow_test",
            evaluated_on="2026-08-19",
            dataset_path="test.jsonl",
            dataset_sha256="0" * 64,
            primary_parser="pypdf==test",
            secondary_parser="pymupdf==test",
        ),
    )

    json_path, markdown_path = write_shadow_parse_artifacts(
        report,
        baseline_dir=tmp_path,
    )

    assert json_path.is_file()
    assert "Fast Parser Shadow Baseline" in markdown_path.read_text(encoding="utf-8")
