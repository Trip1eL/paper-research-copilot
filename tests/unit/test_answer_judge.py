import json
from pathlib import Path

import pytest

from paper_research_copilot.evaluation import (
    AnswerCaseMetrics,
    AnswerCaseResult,
    AnswerEvaluationCase,
    AnswerKeyPoint,
    CachedAnswerJudge,
    JudgeEvaluationConfig,
    RelevantPages,
    build_judge_evaluation_report,
    run_judge_evaluation,
)
from paper_research_copilot.evaluation.answer import EvaluatedCitation, EvaluatedEvidence
from paper_research_copilot.integrations import ChatCompletion, ChatTokenUsage


def _decision_json(score: int = 4) -> str:
    return json.dumps(
        {
            "correctness": {"score": score, "rationale": "correct"},
            "faithfulness": {"score": score, "rationale": "grounded"},
            "citation_completeness": {"score": score, "rationale": "complete"},
            "claim_assessments": [
                {
                    "claim": "The method acts.",
                    "citation_ids": ["C1"],
                    "verdict": "entailed",
                    "rationale": "The cited evidence states it.",
                }
            ],
            "needs_human_review": False,
            "review_reason": "",
        }
    )


class _SequenceJudgeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def complete_with_metadata(self, system_prompt: str, user_prompt: str) -> ChatCompletion:
        response = self.responses[self.calls]
        self.calls += 1
        return ChatCompletion(
            content=response,
            response_model="gpt-5.5-test",
            usage=ChatTokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )


def _case(*, case_id: str = "AE-001", answerable: bool = True) -> AnswerEvaluationCase:
    return AnswerEvaluationCase(
        case_id=case_id,
        question="How does the method act?",
        question_type="method" if answerable else "unanswerable",
        difficulty="medium",
        answerable=answerable,
        relevant=(RelevantPages(paper_id="paper-1", pages=(2,)),) if answerable else (),
        reference_answer="It interleaves reasoning and action." if answerable else "",
        key_points=(
            AnswerKeyPoint(
                key_point_id="KP-01",
                description="interleaves reasoning and action",
                match_any=("reasoning",),
            ),
        )
        if answerable
        else (),
    )


def _result(
    *,
    case_id: str = "AE-001",
    status: str = "answered",
    answer_text: str = "The method acts [C1].",
) -> AnswerCaseResult:
    citation = EvaluatedCitation(
        citation_id="C1",
        chunk_id="chunk-1",
        paper_id="paper-1",
        page_number=2,
    )
    evidence = EvaluatedEvidence(
        rank=1,
        citation_id="C1",
        chunk_id="chunk-1",
        paper_id="paper-1",
        page_number=2,
        score=0.9,
        title="Paper",
        text="The method interleaves reasoning and action.",
    )
    return AnswerCaseResult(
        case_id=case_id,
        source_case_id=None,
        question="How does the method act?",
        question_type="method",
        difficulty="medium",
        answerable=True,
        retrieval_latency_ms=1,
        generation_latency_ms=2,
        total_latency_ms=3,
        answer_status=status,  # type: ignore[arg-type]
        answer_text=answer_text,
        evidence=(evidence,),
        citations=(citation,) if status == "answered" else (),
        metrics=AnswerCaseMetrics(
            generation_succeeded=status != "error",
            answerability_correct=status == "answered",
        ),
    )


def _judge(provider: _SequenceJudgeProvider, cache_path: Path) -> CachedAnswerJudge:
    return CachedAnswerJudge(
        provider,
        model="gpt-5.5",
        cache_path=cache_path,
        retry_attempts=2,
    )


def test_judge_parses_fenced_json_and_retries_invalid_schema(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider(["not-json", f"```json\n{_decision_json()}\n```"])
    record, cache_hit = _judge(provider, tmp_path / "cache.jsonl").judge(
        _case(),
        _result(),
        {},
    )

    assert not cache_hit
    assert provider.calls == 2
    assert record.attempts == 2
    assert record.usage.input_tokens == 20
    assert record.decision.faithfulness.score == 4


def test_judge_cache_hit_avoids_second_model_call(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider([_decision_json()])
    judge = _judge(provider, tmp_path / "cache.jsonl")

    first, first_hit = judge.judge(_case(), _result(), {})
    second, second_hit = judge.judge(_case(), _result(), {})

    assert not first_hit
    assert second_hit
    assert first.input_sha256 == second.input_sha256
    assert provider.calls == 1


def test_changed_answer_invalidates_judge_cache(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider([_decision_json(), _decision_json(3)])
    judge = _judge(provider, tmp_path / "cache.jsonl")

    first, _ = judge.judge(_case(), _result(), {})
    second, cache_hit = judge.judge(
        _case(),
        _result(answer_text="The method reasons before acting [C1]."),
        {},
    )

    assert not cache_hit
    assert first.input_sha256 != second.input_sha256
    assert provider.calls == 2


def test_explicit_cache_keys_keep_repetitions_independent(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider([_decision_json(), _decision_json(3)])
    judge = _judge(provider, tmp_path / "cache.jsonl")

    first, first_hit = judge.judge(_case(), _result(), {}, cache_key="AE-001:R1")
    second, second_hit = judge.judge(_case(), _result(), {}, cache_key="AE-001:R2")

    assert not first_hit
    assert not second_hit
    assert first.case_id == "AE-001:R1"
    assert second.case_id == "AE-001:R2"
    assert provider.calls == 2


def test_generation_failure_and_correct_abstention_are_deterministic(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider([])
    answerable_case = _case(case_id="AE-001")
    unanswerable_case = _case(case_id="AE-002", answerable=False)
    failed = _result(case_id="AE-001", status="error", answer_text="")
    abstained = _result(case_id="AE-002", status="insufficient_evidence", answer_text="")
    abstained = abstained.model_copy(update={"answerable": False})

    results = run_judge_evaluation(
        _judge(provider, tmp_path / "cache.jsonl"),
        (answerable_case, unanswerable_case),
        (failed, abstained),
        evidence_text_by_chunk_id={},
    )

    assert provider.calls == 0
    assert [item.source for item in results] == ["deterministic", "deterministic"]
    assert results[0].decision.correctness.score == 0
    assert results[1].decision.correctness.score == 4


def test_report_keeps_judge_failures_in_overall_denominator(tmp_path: Path) -> None:
    provider = _SequenceJudgeProvider([_decision_json(), "bad-json", "still-bad"])
    cases = (_case(case_id="AE-001"), _case(case_id="AE-002"))
    results = run_judge_evaluation(
        _judge(provider, tmp_path / "cache.jsonl"),
        cases,
        (_result(case_id="AE-001"), _result(case_id="AE-002")),
        evidence_text_by_chunk_id={},
    )
    config = JudgeEvaluationConfig(
        baseline_id="judge_test",
        evaluated_on="2026-08-17",
        dataset_path="evals/dataset.jsonl",
        dataset_sha256="a" * 64,
        answer_baseline_id="answer_test",
        answer_results_path="evals/results.jsonl",
        judge_model="gpt-5.5",
        judge_prompt_version="answer_judge_v1",
        retry_attempts=2,
    )

    report = build_judge_evaluation_report(results, config)

    assert report.case_count == 2
    assert report.judge_failure_count == 1
    assert report.correctness == 0.5
    assert report.failed_cases == ("AE-002",)


def test_judge_rejects_answer_results_with_different_case_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="identical Case IDs"):
        run_judge_evaluation(
            _judge(_SequenceJudgeProvider([]), tmp_path / "cache.jsonl"),
            (_case(case_id="AE-001"),),
            (_result(case_id="AE-999"),),
            evidence_text_by_chunk_id={},
        )
