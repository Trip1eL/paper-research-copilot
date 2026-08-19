"""Offline comparison metrics for interchangeable Research Planner models."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.agent import PlanningResult, ResearchPlan, find_plan_alias_leaks
from paper_research_copilot.evaluation.agent_runtime import AgentEvaluationCase
from paper_research_copilot.integrations import ChatTokenUsage


class PlannerCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    model: str
    case_id: str
    success: bool
    error: str | None = None
    cache_hit: bool
    actual_question_type: str | None = None
    router_correct: bool
    task_count: int = Field(ge=0)
    task_count_correct: bool
    covered_facets: tuple[str, ...] = ()
    task_coverage: float = Field(ge=0, le=1)
    title_leaks: tuple[str, ...] = ()
    attempts: int = Field(ge=1)
    generation_latency_ms: float = Field(ge=0)
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    response_model: str | None = None
    plan: ResearchPlan | None = None


class PlannerVariantSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    model: str
    case_count: int = Field(ge=1)
    planning_success_rate: float = Field(ge=0, le=1)
    router_accuracy: float = Field(ge=0, le=1)
    task_count_accuracy: float = Field(ge=0, le=1)
    task_coverage: float = Field(ge=0, le=1)
    title_leakage_rate: float = Field(ge=0, le=1)
    schema_retry_rate: float = Field(ge=0, le=1)
    p50_generation_latency_ms: float = Field(ge=0)
    p95_generation_latency_ms: float = Field(ge=0)
    known_input_tokens: int = Field(ge=0)
    known_output_tokens: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    quality_gate_passed: bool
    failed_cases: tuple[str, ...]
    route_error_cases: tuple[str, ...]
    task_error_cases: tuple[str, ...]
    leakage_cases: tuple[str, ...]


class PlannerAblationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...]
    prompt_version: str
    retry_attempts: int = Field(ge=1)
    candidate_models: tuple[str, ...]
    quality_gate: str
    notes: tuple[str, ...] = ()


class PlannerAblationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: PlannerAblationConfig
    variants: tuple[PlannerVariantSummary, ...]
    recommended_model: str | None
    recommendation_reason: str


def build_planner_case_result(
    *,
    variant_id: str,
    model: str,
    case: AgentEvaluationCase,
    corpus_aliases: Iterable[str],
    planning: PlanningResult | None,
    error: str | None = None,
    failure_latency_ms: float = 0,
    failure_attempts: int = 1,
) -> PlannerCaseResult:
    if planning is None:
        return PlannerCaseResult(
            variant_id=variant_id,
            model=model,
            case_id=case.case_id,
            success=False,
            error=error or "Unknown Planner failure",
            cache_hit=False,
            router_correct=False,
            task_count=0,
            task_count_correct=False,
            task_coverage=0,
            attempts=failure_attempts,
            generation_latency_ms=failure_latency_ms,
        )
    plan = planning.plan
    covered_facets = match_plan_facets(case, plan)
    return PlannerCaseResult(
        variant_id=variant_id,
        model=model,
        case_id=case.case_id,
        success=True,
        cache_hit=planning.cache_hit,
        actual_question_type=plan.question_type,
        router_correct=plan.question_type == case.expected_question_type,
        task_count=len(plan.tasks),
        task_count_correct=len(plan.tasks) == case.expected_task_count,
        covered_facets=covered_facets,
        task_coverage=len(covered_facets) / len(case.expected_facets),
        title_leaks=find_plan_alias_leaks(plan, corpus_aliases),
        attempts=planning.attempts,
        generation_latency_ms=planning.generation_latency_ms,
        usage=planning.usage,
        response_model=planning.response_model,
        plan=plan,
    )


def match_plan_facets(
    case: AgentEvaluationCase,
    plan: ResearchPlan,
) -> tuple[str, ...]:
    plan_text = "\n".join(f"{task.query}\n{task.goal}" for task in plan.tasks).casefold()
    return tuple(
        facet.facet_id
        for facet in case.expected_facets
        if any(alias.casefold() in plan_text for alias in facet.match_any)
    )


def build_planner_ablation_report(
    results: Sequence[PlannerCaseResult],
    config: PlannerAblationConfig,
) -> PlannerAblationReport:
    if not results:
        raise ValueError("Cannot build a Planner ablation report without results")
    by_variant: defaultdict[str, list[PlannerCaseResult]] = defaultdict(list)
    for result in results:
        by_variant[result.variant_id].append(result)
    expected_cases = set(config.case_ids)
    for variant_id, samples in by_variant.items():
        actual_cases = {sample.case_id for sample in samples}
        if actual_cases != expected_cases or len(samples) != len(expected_cases):
            raise ValueError(
                f"Planner variant {variant_id} does not contain exactly the configured cases"
            )
    variants = tuple(
        _build_variant_summary(variant_id, samples) for variant_id, samples in by_variant.items()
    )
    passing = [variant for variant in variants if variant.quality_gate_passed]
    if passing:
        recommended = min(passing, key=lambda item: item.p50_generation_latency_ms)
        reason = (
            f"{recommended.model} 通过全部质量门槛，并且在通过门槛的候选模型中 "
            f"Planner P50 最低（{recommended.p50_generation_latency_ms:.0f} ms）。"
        )
        recommended_model = recommended.model
    else:
        recommended_model = None
        reason = "没有候选模型通过全部 Planner 质量门槛，保留当前生产模型。"
    return PlannerAblationReport(
        config=config,
        variants=variants,
        recommended_model=recommended_model,
        recommendation_reason=reason,
    )


def build_planner_ablation_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    case_ids: Sequence[str],
    prompt_version: str,
    retry_attempts: int,
    candidate_models: Sequence[str],
    project_root: Path,
    notes: Sequence[str] = (),
) -> PlannerAblationConfig:
    return PlannerAblationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=tuple(case_ids),
        prompt_version=prompt_version,
        retry_attempts=retry_attempts,
        candidate_models=tuple(candidate_models),
        quality_gate=(
            "success=100%; router=100%; task_count=100%; task_coverage=100%; title_leakage=0%"
        ),
        notes=tuple(notes),
    )


def write_planner_ablation_artifacts(
    report: PlannerAblationReport,
    results: Sequence[PlannerCaseResult],
    *,
    baseline_dir: Path,
    diagnostics_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{report.config.baseline_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    diagnostics_path.write_text(
        json.dumps(
            [result.model_dump(mode="json") for result in results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path, diagnostics_path


def _build_variant_summary(
    variant_id: str,
    samples: Sequence[PlannerCaseResult],
) -> PlannerVariantSummary:
    model = samples[0].model
    success_rate = _mean(float(item.success) for item in samples)
    router_accuracy = _mean(float(item.router_correct) for item in samples)
    task_count_accuracy = _mean(float(item.task_count_correct) for item in samples)
    task_coverage = _mean(item.task_coverage for item in samples)
    leakage_rate = _mean(float(bool(item.title_leaks)) for item in samples)
    quality_gate_passed = (
        success_rate == 1
        and router_accuracy == 1
        and task_count_accuracy == 1
        and task_coverage == 1
        and leakage_rate == 0
    )
    return PlannerVariantSummary(
        variant_id=variant_id,
        model=model,
        case_count=len(samples),
        planning_success_rate=success_rate,
        router_accuracy=router_accuracy,
        task_count_accuracy=task_count_accuracy,
        task_coverage=task_coverage,
        title_leakage_rate=leakage_rate,
        schema_retry_rate=_mean(float(item.attempts > 1) for item in samples),
        p50_generation_latency_ms=round(
            _percentile([item.generation_latency_ms for item in samples], 0.50), 2
        ),
        p95_generation_latency_ms=round(
            _percentile([item.generation_latency_ms for item in samples], 0.95), 2
        ),
        known_input_tokens=sum(item.usage.input_tokens or 0 for item in samples),
        known_output_tokens=sum(item.usage.output_tokens or 0 for item in samples),
        model_call_count=sum(item.attempts for item in samples),
        quality_gate_passed=quality_gate_passed,
        failed_cases=tuple(item.case_id for item in samples if not item.success),
        route_error_cases=tuple(item.case_id for item in samples if not item.router_correct),
        task_error_cases=tuple(item.case_id for item in samples if not item.task_count_correct),
        leakage_cases=tuple(item.case_id for item in samples if item.title_leaks),
    )


def _markdown_report(
    report: PlannerAblationReport,
    results: Sequence[PlannerCaseResult],
) -> str:
    lines = [
        f"# Planner Model Ablation：{report.config.baseline_id}",
        "",
        f"- Dataset：`{report.config.dataset_path}`（{len(report.config.case_ids)} Cases）",
        f"- Prompt：`{report.config.prompt_version}`",
        f"- Quality Gate：{report.config.quality_gate}",
        "- 延迟使用原始 generation latency；缓存查找耗时不参与模型对比。",
        "",
        "## 总体结果",
        "",
        "| Model | Success | Router | Task Count | Task Coverage | Title Leakage | "
        "Schema Retry | P50/P95 | Known Input/Output Tokens | Calls | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for summary in report.variants:
        lines.append(
            f"| {summary.model} | {summary.planning_success_rate:.2%} | "
            f"{summary.router_accuracy:.2%} | {summary.task_count_accuracy:.2%} | "
            f"{summary.task_coverage:.2%} | {summary.title_leakage_rate:.2%} | "
            f"{summary.schema_retry_rate:.2%} | {summary.p50_generation_latency_ms:.0f} / "
            f"{summary.p95_generation_latency_ms:.0f} ms | {summary.known_input_tokens} / "
            f"{summary.known_output_tokens} | {summary.model_call_count} | "
            f"{summary.quality_gate_passed} |"
        )
    lines.extend(
        [
            "",
            "## 逐题结果",
            "",
            "| Model | Case | Success | Route | Tasks | Facets | Leakage | Attempts | Latency |",
            "| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for result in results:
        lines.append(
            f"| {result.model} | {result.case_id} | {result.success} | "
            f"{result.actual_question_type or '-'} | {result.task_count} | "
            f"{result.task_coverage:.0%} | {bool(result.title_leaks)} | {result.attempts} | "
            f"{result.generation_latency_ms:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "## 实验说明",
            "",
            *(f"- {note}" for note in report.config.notes),
            "",
            "## 决策",
            "",
            f"- 推荐模型：`{report.recommended_model or '无'}`",
            f"- 原因：{report.recommendation_reason}",
            "- 该决策只覆盖 Planner；Retrieval、Answer 和 Judge 模型没有随本实验改变。",
            "- 8 条 Case 可用于 MVP 选型，但仍需在更大的路由集上复验泛化能力。",
        ]
    )
    return "\n".join(lines) + "\n"


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]
