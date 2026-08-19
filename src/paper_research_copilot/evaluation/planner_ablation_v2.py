"""Strict, acceptable, and core metrics for Planner/Router Evaluation v2."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.agent import PlanningResult, ResearchPlan, find_plan_alias_leaks
from paper_research_copilot.evaluation.planner_datasets import (
    PlannerCaseCategory,
    PlannerRoutingCase,
)
from paper_research_copilot.integrations import ChatTokenUsage


class PlannerV2CaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    model: str
    case_id: str
    category: PlannerCaseCategory
    label_sensitive: bool
    success: bool
    error: str | None = None
    cache_hit: bool
    actual_question_type: str | None = None
    strict_router_correct: bool
    acceptable_router_correct: bool
    task_count: int = Field(ge=0)
    strict_task_count_correct: bool
    acceptable_task_count_correct: bool
    covered_facets: tuple[str, ...] = ()
    task_coverage: float = Field(ge=0, le=1)
    title_leaks: tuple[str, ...] = ()
    attempts: int = Field(ge=1)
    generation_latency_ms: float = Field(ge=0)
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    response_model: str | None = None
    plan: ResearchPlan | None = None


class PlannerCategorySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: PlannerCaseCategory
    case_count: int = Field(ge=1)
    strict_router_accuracy: float = Field(ge=0, le=1)
    acceptable_router_accuracy: float = Field(ge=0, le=1)
    strict_task_count_accuracy: float = Field(ge=0, le=1)
    acceptable_task_count_accuracy: float = Field(ge=0, le=1)
    task_coverage: float = Field(ge=0, le=1)


class PlannerV2VariantSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    model: str
    case_count: int = Field(ge=1)
    core_case_count: int = Field(ge=0)
    label_sensitive_case_count: int = Field(ge=0)
    planning_success_rate: float = Field(ge=0, le=1)
    strict_router_accuracy: float = Field(ge=0, le=1)
    acceptable_router_accuracy: float = Field(ge=0, le=1)
    strict_task_count_accuracy: float = Field(ge=0, le=1)
    acceptable_task_count_accuracy: float = Field(ge=0, le=1)
    task_coverage: float = Field(ge=0, le=1)
    core_router_accuracy: float = Field(ge=0, le=1)
    core_task_count_accuracy: float = Field(ge=0, le=1)
    core_task_coverage: float = Field(ge=0, le=1)
    boundary_strict_router_accuracy: float = Field(ge=0, le=1)
    boundary_acceptable_router_accuracy: float = Field(ge=0, le=1)
    boundary_acceptable_task_count_accuracy: float = Field(ge=0, le=1)
    boundary_task_coverage: float = Field(ge=0, le=1)
    title_leakage_rate: float = Field(ge=0, le=1)
    schema_retry_rate: float = Field(ge=0, le=1)
    p50_generation_latency_ms: float = Field(ge=0)
    p95_generation_latency_ms: float = Field(ge=0)
    known_input_tokens: int = Field(ge=0)
    known_output_tokens: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    quality_gate_passed: bool
    failed_cases: tuple[str, ...]
    strict_route_error_cases: tuple[str, ...]
    unacceptable_route_cases: tuple[str, ...]
    core_task_error_cases: tuple[str, ...]
    low_coverage_cases: tuple[str, ...]
    leakage_cases: tuple[str, ...]
    categories: tuple[PlannerCategorySummary, ...]


class PlannerAblationV2Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...]
    label_sensitive_case_ids: tuple[str, ...]
    prompt_version: str
    retry_attempts: int = Field(ge=1)
    candidate_models: tuple[str, ...]
    quality_gate: str
    notes: tuple[str, ...] = ()


class PlannerAblationV2Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: PlannerAblationV2Config
    variants: tuple[PlannerV2VariantSummary, ...]
    recommended_model: str | None
    recommendation_reason: str


def build_planner_v2_case_result(
    *,
    variant_id: str,
    model: str,
    case: PlannerRoutingCase,
    corpus_aliases: Iterable[str],
    planning: PlanningResult | None,
    error: str | None = None,
    failure_latency_ms: float = 0,
    failure_attempts: int = 1,
) -> PlannerV2CaseResult:
    if planning is None:
        return PlannerV2CaseResult(
            variant_id=variant_id,
            model=model,
            case_id=case.case_id,
            category=case.category,
            label_sensitive=case.label_sensitive,
            success=False,
            error=error or "Unknown Planner failure",
            cache_hit=False,
            strict_router_correct=False,
            acceptable_router_correct=False,
            task_count=0,
            strict_task_count_correct=False,
            acceptable_task_count_correct=False,
            task_coverage=0,
            attempts=failure_attempts,
            generation_latency_ms=failure_latency_ms,
        )
    plan = planning.plan
    covered_facets = match_v2_plan_facets(case, plan)
    return PlannerV2CaseResult(
        variant_id=variant_id,
        model=model,
        case_id=case.case_id,
        category=case.category,
        label_sensitive=case.label_sensitive,
        success=True,
        cache_hit=planning.cache_hit,
        actual_question_type=plan.question_type,
        strict_router_correct=plan.question_type == case.expected_question_type,
        acceptable_router_correct=plan.question_type in case.acceptable_question_types,
        task_count=len(plan.tasks),
        strict_task_count_correct=len(plan.tasks) == case.expected_task_count,
        acceptable_task_count_correct=len(plan.tasks) in case.acceptable_task_counts,
        covered_facets=covered_facets,
        task_coverage=len(covered_facets) / len(case.expected_facets),
        title_leaks=find_plan_alias_leaks(plan, corpus_aliases),
        attempts=planning.attempts,
        generation_latency_ms=planning.generation_latency_ms,
        usage=planning.usage,
        response_model=planning.response_model,
        plan=plan,
    )


def match_v2_plan_facets(
    case: PlannerRoutingCase,
    plan: ResearchPlan,
) -> tuple[str, ...]:
    plan_text = "\n".join(f"{task.query}\n{task.goal}" for task in plan.tasks).casefold()
    return tuple(
        facet.facet_id
        for facet in case.expected_facets
        if any(alias.casefold() in plan_text for alias in facet.match_any)
    )


def build_planner_ablation_v2_report(
    results: Sequence[PlannerV2CaseResult],
    config: PlannerAblationV2Config,
) -> PlannerAblationV2Report:
    if not results:
        raise ValueError("Cannot build a Planner v2 report without results")
    by_variant: defaultdict[str, list[PlannerV2CaseResult]] = defaultdict(list)
    for result in results:
        by_variant[result.variant_id].append(result)
    expected_cases = set(config.case_ids)
    for variant_id, samples in by_variant.items():
        actual_cases = {sample.case_id for sample in samples}
        if actual_cases != expected_cases or len(samples) != len(expected_cases):
            raise ValueError(f"Planner v2 variant {variant_id} has incomplete Cases")
    variants = tuple(
        _build_variant_summary(variant_id, samples) for variant_id, samples in by_variant.items()
    )
    passing = [variant for variant in variants if variant.quality_gate_passed]
    if passing:
        recommended = min(passing, key=lambda item: item.p50_generation_latency_ms)
        recommended_model = recommended.model
        reason = (
            f"{recommended.model} 通过全部 v2 质量门槛，并且在通过门槛的候选模型中 "
            f"P50 最低（{recommended.p50_generation_latency_ms:.0f} ms）。"
        )
    else:
        recommended_model = None
        reason = "没有候选模型通过全部 v2 质量门槛，保留当前生产 Planner。"
    return PlannerAblationV2Report(
        config=config,
        variants=variants,
        recommended_model=recommended_model,
        recommendation_reason=reason,
    )


def build_planner_ablation_v2_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    cases: Sequence[PlannerRoutingCase],
    prompt_version: str,
    retry_attempts: int,
    candidate_models: Sequence[str],
    project_root: Path,
    notes: Sequence[str] = (),
) -> PlannerAblationV2Config:
    return PlannerAblationV2Config(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=tuple(case.case_id for case in cases),
        label_sensitive_case_ids=tuple(case.case_id for case in cases if case.label_sensitive),
        prompt_version=prompt_version,
        retry_attempts=retry_attempts,
        candidate_models=tuple(candidate_models),
        quality_gate=(
            "success=100%; core_router=100%; core_task_count=100%; "
            "task_coverage=100%; acceptable_router=100%; "
            "acceptable_task_count=100%; title_leakage=0%"
        ),
        notes=tuple(notes),
    )


def write_planner_ablation_v2_artifacts(
    report: PlannerAblationV2Report,
    results: Sequence[PlannerV2CaseResult],
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
    samples: Sequence[PlannerV2CaseResult],
) -> PlannerV2VariantSummary:
    core = [item for item in samples if not item.label_sensitive]
    boundary = [item for item in samples if item.label_sensitive]
    success_rate = _mean(float(item.success) for item in samples)
    acceptable_router = _mean(float(item.acceptable_router_correct) for item in samples)
    acceptable_tasks = _mean(float(item.acceptable_task_count_correct) for item in samples)
    core_router = _mean(float(item.strict_router_correct) for item in core)
    core_tasks = _mean(float(item.strict_task_count_correct) for item in core)
    core_coverage = _mean(item.task_coverage for item in core)
    task_coverage = _mean(item.task_coverage for item in samples)
    leakage_rate = _mean(float(bool(item.title_leaks)) for item in samples)
    quality_gate = (
        success_rate == 1
        and core_router == 1
        and core_tasks == 1
        and task_coverage == 1
        and acceptable_router == 1
        and acceptable_tasks == 1
        and leakage_rate == 0
    )
    grouped: defaultdict[PlannerCaseCategory, list[PlannerV2CaseResult]] = defaultdict(list)
    for item in samples:
        grouped[item.category].append(item)
    return PlannerV2VariantSummary(
        variant_id=variant_id,
        model=samples[0].model,
        case_count=len(samples),
        core_case_count=len(core),
        label_sensitive_case_count=len(boundary),
        planning_success_rate=success_rate,
        strict_router_accuracy=_mean(float(item.strict_router_correct) for item in samples),
        acceptable_router_accuracy=acceptable_router,
        strict_task_count_accuracy=_mean(float(item.strict_task_count_correct) for item in samples),
        acceptable_task_count_accuracy=acceptable_tasks,
        task_coverage=task_coverage,
        core_router_accuracy=core_router,
        core_task_count_accuracy=core_tasks,
        core_task_coverage=core_coverage,
        boundary_strict_router_accuracy=_mean(
            float(item.strict_router_correct) for item in boundary
        ),
        boundary_acceptable_router_accuracy=_mean(
            float(item.acceptable_router_correct) for item in boundary
        ),
        boundary_acceptable_task_count_accuracy=_mean(
            float(item.acceptable_task_count_correct) for item in boundary
        ),
        boundary_task_coverage=_mean(item.task_coverage for item in boundary),
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
        quality_gate_passed=quality_gate,
        failed_cases=tuple(item.case_id for item in samples if not item.success),
        strict_route_error_cases=tuple(
            item.case_id for item in samples if not item.strict_router_correct
        ),
        unacceptable_route_cases=tuple(
            item.case_id for item in samples if not item.acceptable_router_correct
        ),
        core_task_error_cases=tuple(
            item.case_id for item in core if not item.strict_task_count_correct
        ),
        low_coverage_cases=tuple(item.case_id for item in samples if item.task_coverage < 1),
        leakage_cases=tuple(item.case_id for item in samples if item.title_leaks),
        categories=tuple(
            _category_summary(category, category_samples)
            for category, category_samples in grouped.items()
        ),
    )


def _category_summary(
    category: PlannerCaseCategory,
    samples: Sequence[PlannerV2CaseResult],
) -> PlannerCategorySummary:
    return PlannerCategorySummary(
        category=category,
        case_count=len(samples),
        strict_router_accuracy=_mean(float(item.strict_router_correct) for item in samples),
        acceptable_router_accuracy=_mean(float(item.acceptable_router_correct) for item in samples),
        strict_task_count_accuracy=_mean(float(item.strict_task_count_correct) for item in samples),
        acceptable_task_count_accuracy=_mean(
            float(item.acceptable_task_count_correct) for item in samples
        ),
        task_coverage=_mean(item.task_coverage for item in samples),
    )


def _markdown_report(
    report: PlannerAblationV2Report,
    results: Sequence[PlannerV2CaseResult],
) -> str:
    lines = [
        f"# Planner Model Ablation v2：{report.config.baseline_id}",
        "",
        f"- Dataset：`{report.config.dataset_path}`（{len(report.config.case_ids)} Cases）",
        f"- Label-sensitive：{len(report.config.label_sensitive_case_ids)} Cases",
        f"- Prompt：`{report.config.prompt_version}`",
        f"- Quality Gate：{report.config.quality_gate}",
        "",
        "## 总体指标",
        "",
        "| Model | Success | Strict Route/Task | Acceptable Route/Task | Coverage | "
        "Core Route/Task/Coverage | Boundary Strict/Acceptable/Coverage | Leakage | Retry | "
        "P50/P95 | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.variants:
        lines.append(
            f"| {item.model} | {item.planning_success_rate:.2%} | "
            f"{item.strict_router_accuracy:.2%} / {item.strict_task_count_accuracy:.2%} | "
            f"{item.acceptable_router_accuracy:.2%} / "
            f"{item.acceptable_task_count_accuracy:.2%} | {item.task_coverage:.2%} | "
            f"{item.core_router_accuracy:.2%} / {item.core_task_count_accuracy:.2%} / "
            f"{item.core_task_coverage:.2%} | "
            f"{item.boundary_strict_router_accuracy:.2%} / "
            f"{item.boundary_acceptable_router_accuracy:.2%} / "
            f"{item.boundary_task_coverage:.2%} | "
            f"{item.title_leakage_rate:.2%} | {item.schema_retry_rate:.2%} | "
            f"{item.p50_generation_latency_ms:.0f} / "
            f"{item.p95_generation_latency_ms:.0f} ms | {item.quality_gate_passed} |"
        )
    lines.extend(["", "## 分类指标", ""])
    for item in report.variants:
        lines.extend(
            [
                f"### {item.model}",
                "",
                "| Category | Cases | Strict Route | Acceptable Route | Strict Task | "
                "Acceptable Task | Coverage |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for category in item.categories:
            lines.append(
                f"| {category.category} | {category.case_count} | "
                f"{category.strict_router_accuracy:.2%} | "
                f"{category.acceptable_router_accuracy:.2%} | "
                f"{category.strict_task_count_accuracy:.2%} | "
                f"{category.acceptable_task_count_accuracy:.2%} | "
                f"{category.task_coverage:.2%} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 调用成本与延迟",
            "",
            "| Model | Calls | Input Tokens | Output Tokens | P50 | P95 | Retry |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant in report.variants:
        lines.append(
            f"| {variant.model} | {variant.model_call_count} | "
            f"{variant.known_input_tokens} | {variant.known_output_tokens} | "
            f"{variant.p50_generation_latency_ms:.0f} ms | "
            f"{variant.p95_generation_latency_ms:.0f} ms | "
            f"{variant.schema_retry_rate:.2%} |"
        )
    lines.append("")
    lines.extend(
        [
            "## 失败审计",
            "",
            "| Model | Failed | Strict Route Errors | Unacceptable Routes | Core Task Errors | "
            "Low Coverage | Leakage |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in report.variants:
        lines.append(
            f"| {item.model} | {_ids(item.failed_cases)} | "
            f"{_ids(item.strict_route_error_cases)} | {_ids(item.unacceptable_route_cases)} | "
            f"{_ids(item.core_task_error_cases)} | {_ids(item.low_coverage_cases)} | "
            f"{_ids(item.leakage_cases)} |"
        )
    lines.extend(
        [
            "",
            "## 逐题结果",
            "",
            "| Model | Case | Category | Route S/A | Tasks S/A | Facets | Attempts | Latency |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for case_result in results:
        lines.append(
            f"| {case_result.model} | {case_result.case_id} | {case_result.category} | "
            f"{case_result.strict_router_correct}/"
            f"{case_result.acceptable_router_correct} | "
            f"{case_result.strict_task_count_correct}/"
            f"{case_result.acceptable_task_count_correct} | "
            f"{case_result.task_coverage:.0%} | {case_result.attempts} | "
            f"{case_result.generation_latency_ms:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "## 决策",
            "",
            f"- 推荐模型：`{report.recommended_model or '无'}`",
            f"- 原因：{report.recommendation_reason}",
            *(f"- {note}" for note in report.config.notes),
        ]
    )
    return "\n".join(lines) + "\n"


def _ids(values: Sequence[str]) -> str:
    return ", ".join(values) or "无"


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]
