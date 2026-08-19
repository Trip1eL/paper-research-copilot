from pathlib import Path

from paper_research_copilot.evaluation.corpus_parse_shadow import (
    CorpusShadowConfig,
    CorpusShadowPaperResult,
    build_corpus_shadow_report,
    write_corpus_shadow_artifacts,
)


def _paper(
    paper_id: str,
    *,
    status: str = "succeeded",
    quarantined: int = 0,
) -> CorpusShadowPaperResult:
    return CorpusShadowPaperResult.model_validate(
        {
            "paper_id": paper_id,
            "slug": paper_id.rpartition(":")[2],
            "status": status,
            "expected_page_count": 10,
            "parsed_page_count": 10 if status == "succeeded" else 0,
            "primary_flagged_pages": 2 if status == "succeeded" else 0,
            "accepted_pages": 9 if quarantined else 10,
            "warning_pages": 0,
            "quarantined_pages": quarantined,
            "secondary_selected_pages": 1 if status == "succeeded" else 0,
            "recovered_pages": 1 if status == "succeeded" else 0,
            "primary_flagged_page_numbers": [9, 10] if status == "succeeded" else [],
            "secondary_selected_page_numbers": [9] if status == "succeeded" else [],
            "warning_page_numbers": [],
            "structured_fallback_pages": [10] if quarantined else [],
            "total_latency_ms": 100 if status == "succeeded" else 0,
            "error": "failed" if status == "failed" else None,
        }
    )


def test_corpus_shadow_report_aggregates_and_writes_artifacts(tmp_path: Path) -> None:
    results = (
        _paper("arxiv:0000.00001", quarantined=1),
        _paper("arxiv:0000.00002"),
        _paper("arxiv:0000.00003", status="failed"),
    )
    report = build_corpus_shadow_report(
        results,
        CorpusShadowConfig(
            report_id="shadow_test",
            evaluated_on="2026-08-19",
            corpus_id="test",
            corpus_version=1,
            primary_parser="pypdf==test",
            secondary_parser="pymupdf==test",
        ),
    )

    json_path, markdown_path = write_corpus_shadow_artifacts(report, output_dir=tmp_path)

    assert report.open_rate == 0.6667
    assert report.page_count == 20
    assert report.selected_quarantined_pages == 1
    assert report.papers_requiring_structured_fallback == ("arxiv:0000.00001",)
    assert json_path.is_file()
    assert "Corpus Parse Shadow" in markdown_path.read_text(encoding="utf-8")
