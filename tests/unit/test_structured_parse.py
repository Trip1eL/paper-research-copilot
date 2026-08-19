from paper_research_copilot.domain.structured_parse import (
    StructuredContentBlock,
    StructuredPageResult,
)
from paper_research_copilot.evaluation.structured_parse import (
    build_structured_parse_config,
    build_structured_parse_report,
    evaluate_structured_parse_case,
    evaluate_table_question,
)
from paper_research_copilot.evaluation.structured_parse_datasets import (
    StructuredParseBenchmarkCase,
    StructuredTableQuestion,
)


def _parsed(table_html: str) -> StructuredPageResult:
    return StructuredPageResult(
        source_path="paper.pdf",
        document_sha256="a" * 64,
        page_number=1,
        parser_name="mineru",
        parser_version="3.4.5",
        backend="pipeline",
        parse_method="ocr",
        device="cpu",
        latency_ms=123.4,
        markdown="# Results\nResearch Copilot",
        blocks=(
            StructuredContentBlock(
                block_id="p0001-b0001",
                page_number=1,
                block_type="table",
                text="Research Copilot 4.33 99.0",
                html=table_html,
                bbox=(10, 20, 900, 800),
                parser_name="mineru",
                parser_version="3.4.5",
                ocr_used=True,
            ),
        ),
        raw_output_dir="output",
    )


def test_table_qa_resolves_rowspan_and_multilevel_column_headers() -> None:
    html = (
        "<table><tr><th rowspan='2'>Model</th><th colspan='2'>SWE-bench Lite</th></tr>"
        "<tr><th>Resolved</th><th>Cost</th></tr>"
        "<tr><td>Claude 3 Opus</td><td>4.33</td><td>99.0</td></tr></table>"
    )
    question = StructuredTableQuestion(
        question="Claude 3 Opus resolved score?",
        row_label="Claude 3 Opus",
        column_headers=("SWE-bench Lite", "Resolved"),
        expected_answer="4.33",
    )

    result = evaluate_table_question(question, _parsed(html))

    assert result.relationship_pass is True
    assert result.actual_answer == "4.33"


def test_table_qa_rejects_answer_that_only_appears_in_wrong_column() -> None:
    html = (
        "<table><tr><th>Model</th><th>Resolved</th><th>Cost</th></tr>"
        "<tr><td>Research Copilot</td><td>4.33</td><td>99.0</td></tr></table>"
    )
    question = StructuredTableQuestion(
        question="Research Copilot cost?",
        row_label="Research Copilot",
        column_headers=("Cost",),
        expected_answer="4.33",
    )

    result = evaluate_table_question(question, _parsed(html))

    assert result.relationship_pass is False
    assert result.actual_answer == "99.0"


def test_structured_case_and_report_require_structure_and_provenance(tmp_path) -> None:
    html = (
        "<table><tr><th>System</th><th>Score</th></tr>"
        "<tr><td>Research Copilot</td><td>96.2</td></tr></table>"
    )
    case = StructuredParseBenchmarkCase(
        case_id="SPB-999",
        source_id="synthetic:test",
        source_revision="v1",
        synthetic=True,
        pdf_path="fixture.pdf",
        pdf_sha256="b" * 64,
        page_number=1,
        category="scanned_table",
        method="ocr",
        expected_contains=("Research Copilot",),
        required_block_types=("table",),
        table_questions=(
            StructuredTableQuestion(
                question="Research Copilot score?",
                row_label="Research Copilot",
                column_headers=("Score",),
                expected_answer="96.2",
            ),
        ),
        notes="Synthetic unit test case.",
    )
    result = evaluate_structured_parse_case(case, _parsed(html))
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    config = build_structured_parse_config(
        baseline_id="test",
        dataset_path=dataset,
        project_root=tmp_path,
        parser_version="3.4.5",
        backend="pipeline",
        device="cpu",
        worker_mode="in_process_pdf_render",
        formula_policy="category_aware",
    )

    report = build_structured_parse_report((result,), config)

    assert result.status == "pass"
    assert report.case_success_rate == 1
    assert report.table_qa_accuracy == 1
    assert report.bbox_provenance_completeness == 1
