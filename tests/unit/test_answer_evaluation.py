import json
from pathlib import Path

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.evaluation import (
    AnswerEvaluationCase,
    AnswerKeyPoint,
    RelevantPages,
    build_answer_evaluation_config,
    build_answer_evaluation_report,
    load_answer_evaluation_cases,
    run_answer_evaluation,
)
from paper_research_copilot.reporting import AnswerGenerator


class _StaticRetriever:
    def __init__(self, evidence: tuple[RetrievedChunk, ...]) -> None:
        self.evidence = evidence

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self.evidence[:top_k]


class _FakeChat:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.answer


def _evidence(number: int, paper_id: str, page: int) -> RetrievedChunk:
    text = f"Evidence for {paper_id}"
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=1 - number / 10,
        chunk=PaperChunk(
            chunk_id=f"chunk-{number}",
            document_sha256="a" * 64,
            chunk_index=number,
            chunking_version="chunking_v1",
            paper_id=paper_id,
            title=f"Paper {paper_id}",
            source_path=f"{paper_id}.pdf",
            page_number=page,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


def _answerable_case() -> AnswerEvaluationCase:
    return AnswerEvaluationCase(
        case_id="AE-001",
        question="How do Alpha and Beta work together?",
        question_type="cross_paper",
        difficulty="hard",
        relevant=(
            RelevantPages(paper_id="paper-a", pages=(1,)),
            RelevantPages(paper_id="paper-b", pages=(2,)),
        ),
        reference_answer="Alpha and Beta cooperate.",
        key_points=(
            AnswerKeyPoint(
                key_point_id="KP-01",
                description="Alpha mechanism",
                match_any=("Alpha",),
            ),
            AnswerKeyPoint(
                key_point_id="KP-02",
                description="Beta mechanism",
                match_any=("Beta",),
            ),
        ),
    )


def test_answer_metrics_separate_key_points_citations_and_strict_pages() -> None:
    results = run_answer_evaluation(
        _StaticRetriever((_evidence(1, "paper-a", 1), _evidence(2, "paper-b", 4))),
        AnswerGenerator(_FakeChat("Alpha is grounded [C1]. Beta is mentioned without support.")),
        (_answerable_case(),),
        top_k=2,
    )

    metrics = results[0].metrics

    assert metrics.generation_succeeded
    assert metrics.answerability_correct
    assert metrics.key_point_recall == 1
    assert metrics.citation_paper_precision == 1
    assert metrics.citation_paper_recall == 0.5
    assert metrics.strict_page_precision == 1
    assert metrics.strict_page_recall == 0.5
    assert metrics.sentence_citation_coverage == 0.5


def test_answer_evaluation_scores_structured_abstention() -> None:
    case = AnswerEvaluationCase(
        case_id="AE-002",
        question="What result is outside this corpus?",
        question_type="unanswerable",
        difficulty="hard",
        answerable=False,
    )
    results = run_answer_evaluation(
        _StaticRetriever((_evidence(1, "paper-a", 1),)),
        AnswerGenerator(_FakeChat("INSUFFICIENT_EVIDENCE")),
        (case,),
        top_k=1,
    )

    assert results[0].answer_status == "insufficient_evidence"
    assert results[0].metrics.answerability_correct


def test_sentence_citation_coverage_accepts_marker_after_punctuation() -> None:
    results = run_answer_evaluation(
        _StaticRetriever((_evidence(1, "paper-a", 1), _evidence(2, "paper-b", 2))),
        AnswerGenerator(_FakeChat("Alpha is supported. [C1] Beta is supported。[C2]")),
        (_answerable_case(),),
        top_k=2,
    )

    assert results[0].metrics.sentence_citation_coverage == 1


def test_answer_report_aggregates_deterministic_metrics(tmp_path: Path) -> None:
    dataset = tmp_path / "answer.jsonl"
    dataset.write_text("{}", encoding="utf-8")
    results = run_answer_evaluation(
        _StaticRetriever((_evidence(1, "paper-a", 1), _evidence(2, "paper-b", 2))),
        AnswerGenerator(_FakeChat("Alpha [C1]. Beta [C2].")),
        (_answerable_case(),),
        top_k=2,
    )
    config = build_answer_evaluation_config(
        baseline_id="answer_test",
        dataset_path=dataset,
        corpus_id="test-corpus",
        corpus_version=1,
        collection_name="test_collection",
        retrieval_strategy="hybrid_rrf",
        retrieval_parameters={},
        answer_model="test-model",
        answer_prompt_version="answer_v1",
        answer_retry_attempts=2,
        top_k=2,
        project_root=tmp_path,
    )

    report = build_answer_evaluation_report(results, config)

    assert report.answerability_accuracy == 1
    assert report.key_point_recall == 1
    assert report.citation_paper_recall == 1
    assert report.strict_page_recall == 1


def test_versioned_answer_dataset_covers_answers_and_abstention() -> None:
    project_root = Path(__file__).parents[2]
    manifest = [
        json.loads(line)
        for line in (project_root / "corpus" / "v2" / "manifest.jsonl")
        .read_text("utf-8")
        .splitlines()
        if line.strip()
    ]
    cases = load_answer_evaluation_cases(
        project_root / "evals" / "datasets" / "answer_generation_v1.jsonl",
        allowed_paper_ids={record["paper_id"] for record in manifest},
        paper_page_counts={record["paper_id"]: record["page_count"] for record in manifest},
    )

    assert len(cases) == 20
    assert sum(case.answerable for case in cases) == 18
    assert sum(not case.answerable for case in cases) == 2
    assert sum(case.question_type == "cross_paper" for case in cases) == 3


def test_v2_answer_dataset_tracks_corpus_expansion_without_rewriting_v1() -> None:
    project_root = Path(__file__).parents[2]
    manifest = [
        json.loads(line)
        for line in (project_root / "corpus" / "v3" / "manifest.jsonl")
        .read_text("utf-8")
        .splitlines()
        if line.strip()
    ]
    v1_cases = load_answer_evaluation_cases(
        project_root / "evals" / "datasets" / "answer_generation_v1.jsonl"
    )
    v2_cases = load_answer_evaluation_cases(
        project_root / "evals" / "datasets" / "answer_generation_v2.jsonl",
        allowed_paper_ids={record["paper_id"] for record in manifest},
        paper_page_counts={record["paper_id"]: record["page_count"] for record in manifest},
    )

    cases_by_id = {case.case_id: case for case in v2_cases}
    assert len(v2_cases) == 32
    assert sum(case.answerable for case in v2_cases) == 31
    assert sum(not case.answerable for case in v2_cases) == 1
    assert sum(case.question_type == "cross_paper" for case in v2_cases) == 7
    assert v2_cases[:19] == v1_cases[:19]
    assert not cases_by_id["AE-019"].answerable
    assert cases_by_id["AE-020"].answerable
    assert cases_by_id["AE-020"].relevant[0].paper_id == "arxiv:2406.12045"
