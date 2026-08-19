"""Repeated-generation stability metrics over frozen retrieval evidence."""

import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.evaluation.answer import AnswerCaseResult
from paper_research_copilot.evaluation.judge import JudgeCaseResult


class StabilityAnswerRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    case_id: str
    repetition: int = Field(ge=1)
    result: AnswerCaseResult


class StabilitySample(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    case_id: str
    repetition: int = Field(ge=1)
    answer: AnswerCaseResult
    judge: JudgeCaseResult


class CaseStabilitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    question_type: str
    run_count: int = Field(ge=1)
    generation_success_rate: float = Field(ge=0, le=1)
    answerability_accuracy: float = Field(ge=0, le=1)
    status_consistent: bool
    unique_answer_count: int = Field(ge=1)
    unique_citation_signature_count: int = Field(ge=1)
    correctness_mean: float = Field(ge=0, le=1)
    correctness_min: float = Field(ge=0, le=1)
    faithfulness_mean: float = Field(ge=0, le=1)
    faithfulness_min: float = Field(ge=0, le=1)
    citation_completeness_mean: float = Field(ge=0, le=1)
    citation_completeness_min: float = Field(ge=0, le=1)
    strict_pass_rate: float = Field(ge=0, le=1)


class VariantStabilitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    case_count: int = Field(ge=1)
    sample_count: int = Field(ge=1)
    generation_success_rate: float = Field(ge=0, le=1)
    answerability_accuracy: float = Field(ge=0, le=1)
    correctness_mean: float = Field(ge=0, le=1)
    mean_case_correctness_stddev: float = Field(ge=0)
    faithfulness_mean: float = Field(ge=0, le=1)
    mean_case_faithfulness_stddev: float = Field(ge=0)
    citation_completeness_mean: float = Field(ge=0, le=1)
    mean_case_citation_completeness_stddev: float = Field(ge=0)
    strict_run_pass_rate: float = Field(ge=0, le=1)
    fully_stable_case_rate: float = Field(ge=0, le=1)
    status_consistency_rate: float = Field(ge=0, le=1)
    citation_consistency_rate: float = Field(ge=0, le=1)
    empty_response_case_rate: float = Field(ge=0, le=1)
    truncation_case_rate: float = Field(ge=0, le=1)
    retry_trigger_rate: float = Field(ge=0, le=1)
    retry_recovery_rate: float = Field(ge=0, le=1)
    finish_reason_counts: dict[str, int]
    p50_generation_latency_ms: float = Field(ge=0)
    p95_generation_latency_ms: float = Field(ge=0)
    cases: tuple[CaseStabilitySummary, ...]


class StabilityEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...]
    repetitions: int = Field(ge=2)
    answer_model: str
    answer_prompt_version: str
    judge_model: str
    judge_prompt_version: str
    evidence_policy: str


class StabilityEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: StabilityEvaluationConfig
    variants: tuple[VariantStabilitySummary, ...]


def build_stability_report(
    samples: Sequence[StabilitySample],
    config: StabilityEvaluationConfig,
) -> StabilityEvaluationReport:
    if not samples:
        raise ValueError("Cannot build a stability report without samples")
    sample_keys = [(sample.baseline_id, sample.case_id, sample.repetition) for sample in samples]
    if len(sample_keys) != len(set(sample_keys)):
        raise ValueError("Stability samples contain duplicate variant/case/repetition keys")

    by_variant: defaultdict[str, list[StabilitySample]] = defaultdict(list)
    for sample in samples:
        if sample.case_id not in config.case_ids:
            raise ValueError(f"Unexpected stability Case ID: {sample.case_id}")
        by_variant[sample.baseline_id].append(sample)

    variants = tuple(
        _variant_summary(baseline_id, variant_samples, config)
        for baseline_id, variant_samples in by_variant.items()
    )
    return StabilityEvaluationReport(config=config, variants=variants)


def build_stability_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    case_ids: Sequence[str],
    repetitions: int,
    answer_model: str,
    answer_prompt_version: str,
    judge_model: str,
    judge_prompt_version: str,
    project_root: Path,
) -> StabilityEvaluationConfig:
    import hashlib

    return StabilityEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=tuple(case_ids),
        repetitions=repetitions,
        answer_model=answer_model,
        answer_prompt_version=answer_prompt_version,
        judge_model=judge_model,
        judge_prompt_version=judge_prompt_version,
        evidence_policy="frozen_top_k_from_answer_baseline",
    )


def write_stability_artifacts(
    report: StabilityEvaluationReport,
    samples: Sequence[StabilitySample],
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
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    raw_path.write_text(
        "\n".join(sample.model_dump_json() for sample in samples) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path, raw_path


def load_answer_cache(path: Path) -> dict[tuple[str, str, int], StabilityAnswerRecord]:
    if not path.is_file():
        return {}
    records = tuple(
        StabilityAnswerRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    keys = [(item.baseline_id, item.case_id, item.repetition) for item in records]
    if len(keys) != len(set(keys)):
        raise ValueError("Answer stability cache contains duplicate keys")
    return {(record.baseline_id, record.case_id, record.repetition): record for record in records}


def write_answer_cache(
    path: Path,
    records: Sequence[StabilityAnswerRecord],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda item: (item.baseline_id, item.case_id, item.repetition))
    path.write_text(
        "\n".join(record.model_dump_json() for record in ordered) + "\n",
        encoding="utf-8",
    )


def _variant_summary(
    baseline_id: str,
    samples: Sequence[StabilitySample],
    config: StabilityEvaluationConfig,
) -> VariantStabilitySummary:
    by_case: defaultdict[str, list[StabilitySample]] = defaultdict(list)
    for sample in samples:
        by_case[sample.case_id].append(sample)
    if set(by_case) != set(config.case_ids):
        raise ValueError(f"{baseline_id} does not contain every configured stability Case")
    if any(len(case_samples) != config.repetitions for case_samples in by_case.values()):
        raise ValueError(
            f"{baseline_id} must contain exactly {config.repetitions} samples per Case"
        )

    case_summaries = tuple(_case_summary(case_id, by_case[case_id]) for case_id in config.case_ids)
    correctness = [_score(sample, "correctness") for sample in samples]
    faithfulness = [_score(sample, "faithfulness") for sample in samples]
    completeness = [_score(sample, "citation_completeness") for sample in samples]
    latencies = [sample.answer.generation_latency_ms for sample in samples]
    traces = [
        sample.answer.generation_trace for sample in samples if sample.answer.generation_trace
    ]
    retry_traces = [trace for trace in traces if trace.retry_triggered]
    finish_reason_counts: dict[str, int] = {}
    for trace in traces:
        for attempt in trace.attempts:
            finish_reason_counts[attempt.finish_reason] = (
                finish_reason_counts.get(attempt.finish_reason, 0) + 1
            )
    return VariantStabilitySummary(
        baseline_id=baseline_id,
        case_count=len(by_case),
        sample_count=len(samples),
        generation_success_rate=_mean(
            float(sample.answer.metrics.generation_succeeded) for sample in samples
        ),
        answerability_accuracy=_mean(
            float(sample.answer.metrics.answerability_correct) for sample in samples
        ),
        correctness_mean=_mean(correctness),
        mean_case_correctness_stddev=_mean(
            statistics.pstdev([_score(sample, "correctness") for sample in case_samples])
            for case_samples in by_case.values()
        ),
        faithfulness_mean=_mean(faithfulness),
        mean_case_faithfulness_stddev=_mean(
            statistics.pstdev([_score(sample, "faithfulness") for sample in case_samples])
            for case_samples in by_case.values()
        ),
        citation_completeness_mean=_mean(completeness),
        mean_case_citation_completeness_stddev=_mean(
            statistics.pstdev([_score(sample, "citation_completeness") for sample in case_samples])
            for case_samples in by_case.values()
        ),
        strict_run_pass_rate=_mean(float(_strict_pass(sample)) for sample in samples),
        fully_stable_case_rate=_mean(
            float(all(_strict_pass(sample) for sample in case_samples))
            for case_samples in by_case.values()
        ),
        status_consistency_rate=_mean(
            float(len({sample.answer.answer_status for sample in case_samples}) == 1)
            for case_samples in by_case.values()
        ),
        citation_consistency_rate=_mean(
            float(len({_citation_signature(sample) for sample in case_samples}) == 1)
            for case_samples in by_case.values()
        ),
        empty_response_case_rate=_mean(
            float(
                sample.answer.generation_trace is not None
                and any(
                    attempt.outcome == "empty"
                    for attempt in sample.answer.generation_trace.attempts
                )
            )
            for sample in samples
        ),
        truncation_case_rate=_mean(
            float(
                sample.answer.generation_trace is not None
                and any(
                    attempt.outcome == "truncated"
                    for attempt in sample.answer.generation_trace.attempts
                )
            )
            for sample in samples
        ),
        retry_trigger_rate=len(retry_traces) / len(samples),
        retry_recovery_rate=(
            _mean(float(trace.retry_recovered) for trace in retry_traces) if retry_traces else 0
        ),
        finish_reason_counts=finish_reason_counts,
        p50_generation_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_generation_latency_ms=round(_percentile(latencies, 0.95), 2),
        cases=case_summaries,
    )


def _case_summary(
    case_id: str,
    samples: Sequence[StabilitySample],
) -> CaseStabilitySummary:
    correctness = [_score(sample, "correctness") for sample in samples]
    faithfulness = [_score(sample, "faithfulness") for sample in samples]
    completeness = [_score(sample, "citation_completeness") for sample in samples]
    return CaseStabilitySummary(
        case_id=case_id,
        question_type=samples[0].answer.question_type,
        run_count=len(samples),
        generation_success_rate=_mean(
            float(sample.answer.metrics.generation_succeeded) for sample in samples
        ),
        answerability_accuracy=_mean(
            float(sample.answer.metrics.answerability_correct) for sample in samples
        ),
        status_consistent=len({sample.answer.answer_status for sample in samples}) == 1,
        unique_answer_count=len(
            {_normalized_answer(sample.answer.answer_text) for sample in samples}
        ),
        unique_citation_signature_count=len({_citation_signature(sample) for sample in samples}),
        correctness_mean=_mean(correctness),
        correctness_min=min(correctness),
        faithfulness_mean=_mean(faithfulness),
        faithfulness_min=min(faithfulness),
        citation_completeness_mean=_mean(completeness),
        citation_completeness_min=min(completeness),
        strict_pass_rate=_mean(float(_strict_pass(sample)) for sample in samples),
    )


def _score(
    sample: StabilitySample,
    field: Literal["correctness", "faithfulness", "citation_completeness"],
) -> float:
    if field == "correctness":
        return sample.judge.decision.correctness.score / 4
    if field == "faithfulness":
        return sample.judge.decision.faithfulness.score / 4
    return sample.judge.decision.citation_completeness.score / 4


def _strict_pass(sample: StabilitySample) -> bool:
    decision = sample.judge.decision
    return (
        sample.answer.metrics.generation_succeeded
        and sample.answer.metrics.answerability_correct
        and decision.correctness.score >= 3
        and decision.faithfulness.score >= 3
        and decision.citation_completeness.score >= 3
    )


def _citation_signature(sample: StabilitySample) -> tuple[tuple[str | None, int], ...]:
    return tuple(
        sorted({(citation.paper_id, citation.page_number) for citation in sample.answer.citations})
    )


def _normalized_answer(answer: str) -> str:
    return " ".join(answer.casefold().split())


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]


def _markdown_report(report: StabilityEvaluationReport) -> str:
    lines = [
        f"# Answer Stability: {report.config.baseline_id}",
        "",
        f"- Cases：{', '.join(report.config.case_ids)}",
        f"- Repetitions：{report.config.repetitions}",
        f"- Evidence：`{report.config.evidence_policy}`",
        f"- Answer / Judge：`{report.config.answer_model}` / `{report.config.judge_model}`",
        "",
        "## 总体结果",
        "",
        "| Variant | Gen Success | Answerability | Correctness | Faithfulness | "
        "Citation Completeness | Strict Runs | Stable Cases | Status / Citation Stable | "
        "Mean within-case Stddev C/F/CC | Gen P50/P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in report.variants:
        lines.append(
            f"| {variant.baseline_id} | {variant.generation_success_rate:.2%} | "
            f"{variant.answerability_accuracy:.2%} | {variant.correctness_mean:.2%} | "
            f"{variant.faithfulness_mean:.2%} | "
            f"{variant.citation_completeness_mean:.2%} | "
            f"{variant.strict_run_pass_rate:.2%} | "
            f"{variant.fully_stable_case_rate:.2%} | "
            f"{variant.status_consistency_rate:.2%} / "
            f"{variant.citation_consistency_rate:.2%} | "
            f"{variant.mean_case_correctness_stddev:.3f} / "
            f"{variant.mean_case_faithfulness_stddev:.3f} / "
            f"{variant.mean_case_citation_completeness_stddev:.3f} | "
            f"{variant.p50_generation_latency_ms:.0f} / "
            f"{variant.p95_generation_latency_ms:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "## 生成终止状态",
            "",
            "| Variant | Empty Cases | Truncated Cases | Retry Trigger | Retry Recovery | "
            "Finish Reasons |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for variant in report.variants:
        lines.append(
            f"| {variant.baseline_id} | {variant.empty_response_case_rate:.2%} | "
            f"{variant.truncation_case_rate:.2%} | {variant.retry_trigger_rate:.2%} | "
            f"{variant.retry_recovery_rate:.2%} | `{variant.finish_reason_counts}` |"
        )
    lines.extend(["", "## 逐 Case 结果", ""])
    for variant in report.variants:
        lines.extend(
            [
                f"### {variant.baseline_id}",
                "",
                "| Case | Status Stable | Unique Answers/Citations | Correctness Mean/Min | "
                "Faithfulness Mean/Min | Completeness Mean/Min | Strict Pass |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for case in variant.cases:
            lines.append(
                f"| {case.case_id} | {case.status_consistent} | "
                f"{case.unique_answer_count}/{case.unique_citation_signature_count} | "
                f"{case.correctness_mean:.2%}/{case.correctness_min:.2%} | "
                f"{case.faithfulness_mean:.2%}/{case.faithfulness_min:.2%} | "
                f"{case.citation_completeness_mean:.2%}/"
                f"{case.citation_completeness_min:.2%} | {case.strict_pass_rate:.2%} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 口径",
            "",
            "- Strict Run 要求生成成功、Answerability 正确，且 Judge 三维均不低于 3/4。",
            "- Stable Case 要求同一 Case 的所有重复运行都通过 Strict Run。",
            "- Citation Stable 要求每次运行引用的论文/页码集合完全一致。",
            "- 本实验冻结每个 Answer Baseline 的 Top-K Evidence，只测量生成与引用选择波动。",
        ]
    )
    return "\n".join(lines) + "\n"
