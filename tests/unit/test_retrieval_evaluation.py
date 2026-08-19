from pathlib import Path

import pytest

from paper_research_copilot.evaluation import (
    RelevantPages,
    RetrievalCaseResult,
    RetrievalEvaluationConfig,
    build_evaluation_report,
    write_evaluation_artifacts,
)
from paper_research_copilot.evaluation.datasets import RetrievalDiagnosticCase
from paper_research_copilot.evaluation.retrieval import RetrievedCandidate, run_retrieval_evaluation


def _candidate(rank: int, paper_id: str, page: int) -> RetrievedCandidate:
    return RetrievedCandidate(
        rank=rank,
        score=1 - rank / 10,
        chunk_id=f"chunk-{rank}",
        paper_id=paper_id,
        page_number=page,
        section_title="Method",
        title=f"Paper {paper_id}",
    )


def _config() -> RetrievalEvaluationConfig:
    return RetrievalEvaluationConfig(
        baseline_id="test_dense",
        evaluated_on="2026-08-16",
        dataset_path="evals/dataset.jsonl",
        dataset_sha256="a" * 64,
        corpus_id="test-corpus",
        corpus_version=1,
        collection_name="test_collection",
        embedding_model="test-embedding",
        chunking_version="chunking_v1",
        retrieval_strategy="dense",
        strategy_parameters={},
        top_k=5,
        cutoffs=(1, 2, 5),
    )


def test_metrics_separate_paper_and_exact_page_coverage() -> None:
    result = RetrievalCaseResult(
        case_id="RD-001",
        question="Compare A and B",
        question_type="cross_paper",
        difficulty="hard",
        relevant=(
            RelevantPages(paper_id="paper-a", pages=(1,)),
            RelevantPages(paper_id="paper-b", pages=(2,)),
        ),
        latency_ms=10,
        candidates=(
            _candidate(1, "paper-a", 3),
            _candidate(2, "paper-a", 1),
            _candidate(3, "paper-c", 1),
            _candidate(4, "paper-b", 2),
            _candidate(5, "paper-b", 2),
        ),
    )

    report = build_evaluation_report((result,), _config())

    assert report.overall.cutoffs[1].paper_recall == 0.5
    assert report.overall.cutoffs[1].exact_page_recall == 0
    assert report.overall.cutoffs[2].exact_page_recall == 0.5
    assert report.overall.cutoffs[5].paper_recall == 1
    assert report.overall.cutoffs[5].exact_page_recall == 1
    assert report.overall.cutoffs[5].same_page_redundancy_rate == pytest.approx(0.2)
    assert report.overall.paper_mrr == 1
    assert report.overall.exact_page_mrr == 0.5


def test_evaluation_artifacts_include_summary_and_raw_results(tmp_path: Path) -> None:
    result = RetrievalCaseResult(
        case_id="RD-001",
        question="Find A",
        question_type="fact",
        difficulty="easy",
        relevant=(RelevantPages(paper_id="paper-a", pages=(1,)),),
        latency_ms=10,
        candidates=(_candidate(1, "paper-a", 1),),
    )
    report = build_evaluation_report((result,), _config())

    json_path, markdown_path, raw_path = write_evaluation_artifacts(
        report,
        (result,),
        baseline_dir=tmp_path / "baselines",
        results_dir=tmp_path / "results",
    )

    assert json_path.is_file()
    assert "Paper Recall" in markdown_path.read_text(encoding="utf-8")
    assert '"case_id":"RD-001"' in raw_path.read_text(encoding="utf-8")


class _EmptyRetriever:
    def retrieve(self, question: str, top_k: int):  # type: ignore[no-untyped-def]
        return ()


def _diagnostic(case_id: str, tag: str) -> RetrievalDiagnosticCase:
    return RetrievalDiagnosticCase(
        case_id=case_id,
        question="How does this retrieval method work?",
        question_type="method",
        difficulty="hard",
        subset="discovery",
        contains_paper_name=False,
        relevant=(RelevantPages(paper_id="paper-a", pages=(1,)),),
        evidence_hint="Method evidence on the relevant page.",
        tags=(tag,),
    )


def test_report_separates_paired_anchors_and_challenge_cases() -> None:
    results = run_retrieval_evaluation(
        _EmptyRetriever(),
        (
            _diagnostic("DS-001", "anchor-v1"),
            _diagnostic("DS-026", "same-topic-distractor"),
        ),
        top_k=5,
    )

    report = build_evaluation_report(results, _config())

    assert [result.evaluation_split for result in results] == ["paired_anchor", "challenge"]
    assert {group.group: group.case_count for group in report.by_evaluation_split} == {
        "challenge": 1,
        "paired_anchor": 1,
    }
