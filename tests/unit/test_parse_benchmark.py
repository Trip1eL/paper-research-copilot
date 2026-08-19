from pathlib import Path

from paper_research_copilot.evaluation.parse_benchmark import (
    ParseBenchmarkConfig,
    build_parse_benchmark_report,
    calculate_character_metrics,
    run_parse_benchmark,
    write_parse_benchmark_artifacts,
)
from paper_research_copilot.evaluation.parse_datasets import ParseBenchmarkCase


def _case(**overrides: object) -> ParseBenchmarkCase:
    record: dict[str, object] = {
        "case_id": "PB-001",
        "paper_id": "arxiv:0000.00000",
        "arxiv_version": "0000.00000v1",
        "pdf_path": "paper.pdf",
        "pdf_sha256": "0" * 64,
        "page_number": 1,
        "category": "normal_text",
        "visual_text_present": True,
        "expected_text_layer": True,
        "expected_contains": ["Useful text"],
        "table_questions": [],
        "notes": "Unit test fixture.",
    }
    record.update(overrides)
    return ParseBenchmarkCase.model_validate(record)


def _config() -> ParseBenchmarkConfig:
    return ParseBenchmarkConfig(
        baseline_id="parse_test",
        evaluated_on="2026-08-19",
        dataset_path="evals/datasets/test.jsonl",
        dataset_sha256="0" * 64,
        parser_version="test",
        short_page_char_threshold=200,
        control_ratio_threshold=0.002,
        replacement_ratio_threshold=0.001,
    )


def test_character_metrics_cover_suspicious_character_classes() -> None:
    metrics = calculate_character_metrics("text\ufffd\x03\ue000")

    assert metrics.char_count == 7
    assert metrics.replacement_char_count == 1
    assert metrics.control_char_count == 1
    assert metrics.private_use_char_count == 1
    assert metrics.non_printable_char_count == 2


def test_run_parse_benchmark_marks_short_and_checks_anchors(tmp_path: Path) -> None:
    case = _case()
    calls: list[tuple[Path, int]] = []

    def extractor(path: Path, page_number: int) -> tuple[str, float]:
        calls.append((path, page_number))
        return "Useful\ntext", 12.345

    result = run_parse_benchmark(
        (case,),
        project_root=tmp_path,
        extractor=extractor,
    )[0]

    assert calls == [((tmp_path / "paper.pdf").resolve(), 1)]
    assert result.status == "short"
    assert result.expected_contains_pass
    assert result.extract_latency_ms == 12.35


def test_run_parse_benchmark_checks_table_answer_and_context(tmp_path: Path) -> None:
    case = _case(
        category="native_table_simple",
        table_questions=[
            {
                "question": "What is the score?",
                "expected_answer": "72.36%",
                "required_context": ["Human Performance", "Overall"],
            }
        ],
    )

    result = run_parse_benchmark(
        (case,),
        project_root=tmp_path,
        extractor=lambda path, page: (
            "Useful text Overall Human Performance 72.36%" + " x" * 100,
            1.0,
        ),
    )[0]

    assert result.table_questions_pass is True
    assert result.table_question_results[0].answer_present
    assert result.table_question_results[0].context_anchors_pass


def test_report_and_artifacts_do_not_store_full_page_text(tmp_path: Path) -> None:
    case = _case()
    result = run_parse_benchmark(
        (case,),
        project_root=tmp_path,
        extractor=lambda path, page: ("Useful text " + "x" * 500, 2.0),
    )[0]
    report = build_parse_benchmark_report((result,), _config())

    json_path, markdown_path = write_parse_benchmark_artifacts(
        report,
        baseline_dir=tmp_path / "baselines",
    )

    assert report.case_count == 1
    assert report.expected_anchor_pass_rate == 1
    assert len(result.preview) == 240
    assert "x" * 300 not in json_path.read_text(encoding="utf-8")
    assert "PDF Parse Baseline" in markdown_path.read_text(encoding="utf-8")
