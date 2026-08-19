from pathlib import Path

from paper_research_copilot.evaluation import (
    AnswerCaseMetrics,
    AnswerCaseResult,
    JudgeCaseResult,
    JudgeDecision,
    JudgeDimension,
    StabilityAnswerRecord,
    StabilityEvaluationConfig,
    StabilitySample,
    build_stability_report,
    load_answer_cache,
    write_answer_cache,
)
from paper_research_copilot.evaluation.answer import EvaluatedCitation
from paper_research_copilot.integrations import ChatTokenUsage


def _answer(
    case_id: str,
    *,
    status: str = "answered",
    page: int = 1,
    answerability_correct: bool = True,
) -> AnswerCaseResult:
    return AnswerCaseResult(
        case_id=case_id,
        source_case_id=None,
        question="How does the method work?",
        question_type="method",
        difficulty="hard",
        answerable=True,
        retrieval_latency_ms=0,
        generation_latency_ms=100,
        total_latency_ms=100,
        answer_status=status,  # type: ignore[arg-type]
        answer_text="Grounded answer [C1]." if status == "answered" else "",
        evidence=(),
        citations=(
            EvaluatedCitation(
                citation_id="C1",
                chunk_id=f"chunk-{page}",
                paper_id="paper-a",
                page_number=page,
            ),
        )
        if status == "answered"
        else (),
        metrics=AnswerCaseMetrics(
            generation_succeeded=True,
            answerability_correct=answerability_correct,
        ),
    )


def _sample(
    case_id: str,
    repetition: int,
    score: int,
    *,
    status: str = "answered",
    page: int = 1,
    answerability_correct: bool = True,
) -> StabilitySample:
    dimension = JudgeDimension(score=score, rationale="test")
    answer = _answer(
        case_id,
        status=status,
        page=page,
        answerability_correct=answerability_correct,
    )
    return StabilitySample(
        baseline_id="variant-a",
        case_id=case_id,
        repetition=repetition,
        answer=answer,
        judge=JudgeCaseResult(
            case_id=case_id,
            answer_status=answer.answer_status,
            source="deterministic",
            model_latency_ms=0,
            attempts=0,
            usage=ChatTokenUsage(),
            decision=JudgeDecision(
                correctness=dimension,
                faithfulness=dimension,
                citation_completeness=dimension,
                claim_assessments=(),
                needs_human_review=False,
            ),
        ),
    )


def _config() -> StabilityEvaluationConfig:
    return StabilityEvaluationConfig(
        baseline_id="stability-test",
        evaluated_on="2026-08-17",
        dataset_path="evals/test.jsonl",
        dataset_sha256="a" * 64,
        case_ids=("AE-001", "AE-002"),
        repetitions=2,
        answer_model="answer-model",
        answer_prompt_version="answer-v1",
        judge_model="judge-model",
        judge_prompt_version="judge-v1",
        evidence_policy="frozen_top_k_from_answer_baseline",
    )


def test_stability_report_exposes_status_citation_and_score_variance() -> None:
    report = build_stability_report(
        (
            _sample("AE-001", 1, 4),
            _sample(
                "AE-001",
                2,
                2,
                status="insufficient_evidence",
                page=2,
                answerability_correct=False,
            ),
            _sample("AE-002", 1, 4),
            _sample("AE-002", 2, 4),
        ),
        _config(),
    )

    variant = report.variants[0]
    assert variant.correctness_mean == 0.875
    assert variant.strict_run_pass_rate == 0.75
    assert variant.fully_stable_case_rate == 0.5
    assert variant.status_consistency_rate == 0.5
    assert variant.citation_consistency_rate == 0.5
    assert variant.cases[0].correctness_min == 0.5


def test_stability_answer_cache_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "answers.jsonl"
    record = StabilityAnswerRecord(
        baseline_id="variant-a",
        case_id="AE-001",
        repetition=1,
        result=_answer("AE-001"),
    )

    write_answer_cache(path, (record,))
    loaded = load_answer_cache(path)

    assert loaded[("variant-a", "AE-001", 1)] == record
