"""Cached, observable LLM Judge for answer correctness and citation grounding."""

import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.evaluation.answer import AnswerCaseResult
from paper_research_copilot.evaluation.answer_datasets import AnswerEvaluationCase
from paper_research_copilot.evaluation.judge_prompts import (
    JUDGE_PROMPT_VERSION,
    JUDGE_SYSTEM_PROMPT,
    build_judge_user_prompt,
)
from paper_research_copilot.integrations import (
    ChatCompletion,
    ChatTokenUsage,
    ObservableChatProvider,
)


class JudgeDimension(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: int = Field(ge=0, le=4)
    rationale: str = Field(min_length=1)


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim: str = Field(min_length=1)
    citation_ids: tuple[str, ...]
    verdict: Literal["entailed", "partially_entailed", "unsupported"]
    rationale: str = Field(min_length=1)


class JudgeDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    correctness: JudgeDimension
    faithfulness: JudgeDimension
    citation_completeness: JudgeDimension
    claim_assessments: tuple[ClaimAssessment, ...] = Field(max_length=12)
    needs_human_review: bool
    review_reason: str = ""

    @model_validator(mode="after")
    def validate_review_reason(self) -> "JudgeDecision":
        if self.needs_human_review and not self.review_reason.strip():
            raise ValueError("Human-review decisions require a review reason")
        return self


class JudgeRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: str
    prompt_version: str
    latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=1)
    usage: ChatTokenUsage
    response_model: str | None = None
    raw_response: str
    decision: JudgeDecision


class JudgeCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    answer_status: str
    source: Literal["llm", "cache", "deterministic", "judge_error"]
    input_sha256: str | None = None
    model_latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=0)
    usage: ChatTokenUsage
    decision: JudgeDecision
    error: str | None = None


class JudgeEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_baseline_id: str
    answer_results_path: str
    judge_model: str
    judge_prompt_version: str
    retry_attempts: int = Field(ge=1)


class JudgeEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: JudgeEvaluationConfig
    case_count: int = Field(ge=1)
    llm_judged_count: int = Field(ge=0)
    deterministic_count: int = Field(ge=0)
    cache_hit_count: int = Field(ge=0)
    judge_failure_count: int = Field(ge=0)
    correctness: float = Field(ge=0, le=1)
    faithfulness: float = Field(ge=0, le=1)
    citation_completeness: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    human_review_rate: float = Field(ge=0, le=1)
    mean_model_latency_ms: float = Field(ge=0)
    p50_model_latency_ms: float = Field(ge=0)
    p95_model_latency_ms: float = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    failed_cases: tuple[str, ...]
    human_review_cases: tuple[str, ...]


class CachedAnswerJudge:
    def __init__(
        self,
        provider: ObservableChatProvider,
        *,
        model: str,
        cache_path: Path,
        retry_attempts: int = 3,
    ) -> None:
        if retry_attempts < 1:
            raise ValueError("Retry attempts must be at least 1")
        self._provider = provider
        self.model = model
        self.cache_path = cache_path
        self.retry_attempts = retry_attempts
        self._records = self._load_cache()

    def judge(
        self,
        case: AnswerEvaluationCase,
        result: AnswerCaseResult,
        evidence_text_by_chunk_id: Mapping[str, str],
        *,
        cache_key: str | None = None,
    ) -> tuple[JudgeRecord, bool]:
        user_prompt = build_judge_user_prompt(case, result, evidence_text_by_chunk_id)
        record_key = cache_key or case.case_id
        input_sha256 = _judge_input_hash(record_key, JUDGE_SYSTEM_PROMPT, user_prompt)
        cached = self._records.get(record_key)
        if (
            cached is not None
            and cached.input_sha256 == input_sha256
            and cached.model == self.model
            and cached.prompt_version == JUDGE_PROMPT_VERSION
        ):
            return cached, True

        started = time.perf_counter()
        completions: list[ChatCompletion] = []
        last_error: ValueError | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                completion = self._provider.complete_with_metadata(
                    JUDGE_SYSTEM_PROMPT,
                    user_prompt,
                )
                completions.append(completion)
                decision = _parse_judge_decision(completion.content)
                record = JudgeRecord(
                    case_id=record_key,
                    input_sha256=input_sha256,
                    model=self.model,
                    prompt_version=JUDGE_PROMPT_VERSION,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    attempts=attempt,
                    usage=_sum_usage(completions),
                    response_model=completion.response_model,
                    raw_response=completion.content,
                    decision=decision,
                )
                self._records[record_key] = record
                self._write_cache()
                return record, False
            except ValueError as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
        raise ValueError(
            f"Judge failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error

    def _load_cache(self) -> dict[str, JudgeRecord]:
        if not self.cache_path.is_file():
            return {}
        return {
            record.case_id: record
            for line in self.cache_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for record in (JudgeRecord.model_validate_json(line),)
        }

    def _write_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            self._records[case_id].model_dump_json() for case_id in sorted(self._records)
        )
        self.cache_path.write_text(content + "\n", encoding="utf-8")


def run_judge_evaluation(
    judge: CachedAnswerJudge,
    cases: Sequence[AnswerEvaluationCase],
    answer_results: Sequence[AnswerCaseResult],
    *,
    evidence_text_by_chunk_id: Mapping[str, str],
    cache_key_by_case_id: Mapping[str, str] | None = None,
    progress: Callable[[JudgeCaseResult, int, int], None] | None = None,
) -> tuple[JudgeCaseResult, ...]:
    cases_by_id = {case.case_id: case for case in cases}
    result_ids = [result.case_id for result in answer_results]
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("Answer results contain duplicate case IDs")
    if set(result_ids) != set(cases_by_id):
        raise ValueError("Answer results and Judge dataset must contain identical Case IDs")

    judged_results: list[JudgeCaseResult] = []
    for index, answer_result in enumerate(answer_results, start=1):
        case = cases_by_id[answer_result.case_id]
        deterministic = _deterministic_decision(case, answer_result)
        if deterministic is not None:
            judged = JudgeCaseResult(
                case_id=case.case_id,
                answer_status=answer_result.answer_status,
                source="deterministic",
                model_latency_ms=0,
                attempts=0,
                usage=ChatTokenUsage(),
                decision=deterministic,
            )
        else:
            try:
                record, cache_hit = judge.judge(
                    case,
                    answer_result,
                    evidence_text_by_chunk_id,
                    cache_key=(
                        cache_key_by_case_id.get(case.case_id) if cache_key_by_case_id else None
                    ),
                )
                judged = JudgeCaseResult(
                    case_id=case.case_id,
                    answer_status=answer_result.answer_status,
                    source="cache" if cache_hit else "llm",
                    input_sha256=record.input_sha256,
                    model_latency_ms=record.latency_ms,
                    attempts=record.attempts,
                    usage=record.usage,
                    decision=record.decision,
                )
            except Exception as exc:  # A Judge failure must not erase other Case results.
                judged = JudgeCaseResult(
                    case_id=case.case_id,
                    answer_status=answer_result.answer_status,
                    source="judge_error",
                    model_latency_ms=0,
                    attempts=judge.retry_attempts,
                    usage=ChatTokenUsage(),
                    decision=_zero_decision("Judge invocation or schema validation failed."),
                    error=f"{type(exc).__name__}: {exc}",
                )
        judged_results.append(judged)
        if progress:
            progress(judged, index, len(answer_results))
    return tuple(judged_results)


def _deterministic_decision(
    case: AnswerEvaluationCase,
    result: AnswerCaseResult,
) -> JudgeDecision | None:
    if result.answer_status == "error":
        return _zero_decision("Answer generation failed; all answer-quality dimensions score zero.")
    if case.answerable and result.answer_status == "insufficient_evidence":
        return _zero_decision("The system refused an answerable Golden Case.")
    if not case.answerable and result.answer_status == "insufficient_evidence":
        return _perfect_decision("The system correctly refused an out-of-corpus question.")
    if not case.answerable:
        return _zero_decision("The system answered a Golden Case marked unanswerable.")
    return None


def build_judge_evaluation_report(
    results: Sequence[JudgeCaseResult],
    config: JudgeEvaluationConfig,
) -> JudgeEvaluationReport:
    if not results:
        raise ValueError("Cannot build a Judge report without Case results")
    model_latencies = [
        result.model_latency_ms for result in results if result.source in {"llm", "cache"}
    ]
    correctness = _mean(result.decision.correctness.score / 4 for result in results)
    faithfulness = _mean(result.decision.faithfulness.score / 4 for result in results)
    completeness = _mean(result.decision.citation_completeness.score / 4 for result in results)
    return JudgeEvaluationReport(
        config=config,
        case_count=len(results),
        llm_judged_count=sum(result.source in {"llm", "cache"} for result in results),
        deterministic_count=sum(result.source == "deterministic" for result in results),
        cache_hit_count=sum(result.source == "cache" for result in results),
        judge_failure_count=sum(result.source == "judge_error" for result in results),
        correctness=correctness,
        faithfulness=faithfulness,
        citation_completeness=completeness,
        overall_score=(correctness + faithfulness + completeness) / 3,
        human_review_rate=_mean(float(result.decision.needs_human_review) for result in results),
        mean_model_latency_ms=round(_mean(model_latencies), 2),
        p50_model_latency_ms=round(_percentile(model_latencies, 0.50), 2),
        p95_model_latency_ms=round(_percentile(model_latencies, 0.95), 2),
        total_input_tokens=sum(result.usage.input_tokens or 0 for result in results),
        total_output_tokens=sum(result.usage.output_tokens or 0 for result in results),
        failed_cases=tuple(
            result.case_id
            for result in results
            if result.source == "judge_error" or result.decision.correctness.score == 0
        ),
        human_review_cases=tuple(
            result.case_id for result in results if result.decision.needs_human_review
        ),
    )


def build_judge_evaluation_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    answer_baseline_id: str,
    answer_results_path: Path,
    judge_model: str,
    retry_attempts: int,
    project_root: Path,
) -> JudgeEvaluationConfig:
    return JudgeEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        answer_baseline_id=answer_baseline_id,
        answer_results_path=(
            answer_results_path.resolve().relative_to(project_root.resolve()).as_posix()
        ),
        judge_model=judge_model,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        retry_attempts=retry_attempts,
    )


def write_judge_evaluation_artifacts(
    report: JudgeEvaluationReport,
    results: Sequence[JudgeCaseResult],
    *,
    baseline_dir: Path,
    results_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    raw_path = results_dir / f"{report.config.baseline_id}.jsonl"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    raw_path.write_text(
        "\n".join(result.model_dump_json() for result in results) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path, raw_path


def _markdown_report(
    report: JudgeEvaluationReport,
    results: Sequence[JudgeCaseResult],
) -> str:
    lines = [
        f"# LLM Judge Baseline: {report.config.baseline_id}",
        "",
        f"- Answer Baseline：`{report.config.answer_baseline_id}`",
        f"- Judge：`{report.config.judge_model}` / `{report.config.judge_prompt_version}`",
        f"- Cases：{report.case_count}（LLM={report.llm_judged_count}, "
        f"deterministic={report.deterministic_count}, cache={report.cache_hit_count}）",
        "",
        "## 总体指标",
        "",
        "| Correctness | Faithfulness | Citation Completeness | Overall | Human Review | "
        "Judge P50/P95 | Input/Output Tokens |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.correctness:.2%} | {report.faithfulness:.2%} | "
        f"{report.citation_completeness:.2%} | {report.overall_score:.2%} | "
        f"{report.human_review_rate:.2%} | {report.p50_model_latency_ms:.0f} / "
        f"{report.p95_model_latency_ms:.0f} ms | {report.total_input_tokens} / "
        f"{report.total_output_tokens} |",
        "",
        "## 逐题结果",
        "",
        "| Case | Source | Correctness | Faithfulness | Citation Completeness | Review | Latency |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for result in results:
        decision = result.decision
        lines.append(
            f"| {result.case_id} | {result.source} | {decision.correctness.score}/4 | "
            f"{decision.faithfulness.score}/4 | {decision.citation_completeness.score}/4 | "
            f"{decision.needs_human_review} | {result.model_latency_ms:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "## 审计信息",
            "",
            f"- Judge failures：{', '.join(report.failed_cases) or '无'}",
            f"- Human review：{', '.join(report.human_review_cases) or '无'}",
            "- 0 分包含 Generation Failure、错误拒答和 Judge Failure，避免只统计成功样本。",
            "- LLM Judge 与确定性指标并列使用，不覆盖 Answer、Evidence、Citation 或延迟。",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_judge_decision(response: str) -> JudgeDecision:
    cleaned = response.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Judge must return valid JSON") from exc
    return JudgeDecision.model_validate(payload)


def _judge_input_hash(case_id: str, system_prompt: str, user_prompt: str) -> str:
    payload = json.dumps(
        {"case_id": case_id, "system_prompt": system_prompt, "user_prompt": user_prompt},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sum_usage(completions: Sequence[ChatCompletion]) -> ChatTokenUsage:
    input_values = [item.usage.input_tokens for item in completions]
    output_values = [item.usage.output_tokens for item in completions]
    total_values = [item.usage.total_tokens for item in completions]
    return ChatTokenUsage(
        input_tokens=_sum_known(input_values),
        output_tokens=_sum_known(output_values),
        total_tokens=_sum_known(total_values),
    )


def _sum_known(values: Sequence[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _zero_decision(reason: str) -> JudgeDecision:
    return _uniform_decision(0, reason)


def _perfect_decision(reason: str) -> JudgeDecision:
    return _uniform_decision(4, reason)


def _uniform_decision(score: int, reason: str) -> JudgeDecision:
    dimension = JudgeDimension(score=score, rationale=reason)
    return JudgeDecision(
        correctness=dimension,
        faithfulness=dimension,
        citation_completeness=dimension,
        claim_assessments=(),
        needs_human_review=False,
    )


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]
