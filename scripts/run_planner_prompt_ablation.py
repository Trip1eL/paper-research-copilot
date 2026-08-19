"""Evaluate the corpus-verification Planner prompt on full and stability sets."""

import argparse
import json
import re
import time
from pathlib import Path

from paper_research_copilot.agent import (
    CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
    CachedResearchPlanner,
)
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import (
    PlannerAblationV2Report,
    PlannerRoutingCase,
    PlannerV2CaseResult,
    build_planner_ablation_v2_config,
    build_planner_ablation_v2_report,
    build_planner_v2_case_result,
    load_planner_routing_cases,
    write_planner_ablation_v2_artifacts,
)
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider

STABILITY_CASE_IDS = (
    "PR-016",
    "PR-032",
    "PR-033",
    "PR-034",
    "PR-035",
    "PR-036",
    "PR-037",
    "PR-038",
    "PR-039",
    "PR-040",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "planner_routing_v2.jsonl",
    )
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--baseline-id", default="planner_prompt_ablation_v2")
    parser.add_argument(
        "--v1-baseline",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines" / "planner_model_ablation_v2.json",
    )
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data" / "agent")
    args = parser.parse_args()
    if args.repetitions < 2:
        raise ValueError("Planner prompt stability requires at least two repetitions")
    if args.retry_attempts < 1:
        raise ValueError("Planner retry attempts must be positive")

    cases = load_planner_routing_cases(args.dataset)
    cases_by_id = {case.case_id: case for case in cases}
    stability_cases = tuple(cases_by_id[case_id] for case_id in STABILITY_CASE_IDS)
    settings = get_settings()
    llm_url, llm_key = settings.require_llm_credentials()
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    aliases = tuple(
        alias
        for asset in catalog.papers
        for alias in (
            asset.spec.slug,
            asset.spec.title,
            asset.spec.title.partition(":")[0],
        )
    )

    def planner_for(repetition: int) -> CachedResearchPlanner:
        safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.deepseek_model)
        return CachedResearchPlanner(
            OpenAICompatibleChatProvider(
                base_url=llm_url,
                api_key=llm_key,
                model=settings.deepseek_model,
                max_tokens=settings.agent_planner_max_tokens,
            ),
            model=settings.deepseek_model,
            cache_path=args.cache_dir / f"research_plans_v2_{safe_model}_r{repetition}.jsonl",
            forbidden_aliases=aliases,
            retry_attempts=args.retry_attempts,
            prompt_version=CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
        )

    first_planner = planner_for(1)
    full_results = _run_cases(
        first_planner,
        cases,
        variant_id="deepseek_prompt_v2_full",
        model=settings.deepseek_model,
        aliases=aliases,
        progress_prefix="full",
    )
    full_report = _report(
        results=full_results,
        cases=cases,
        baseline_id=f"{args.baseline_id}_full",
        dataset=args.dataset,
        retry_attempts=args.retry_attempts,
        candidates=(settings.deepseek_model,),
        notes=(
            "DeepSeek 使用 corpus-verification Prompt v2；与 v1 保持相同 Schema、max_tokens、"
            "重试和泄漏审计。",
            "全集 Gate 用于检查定向 Prompt 是否对其他问题类别产生回退。",
        ),
    )
    _write_report(full_report, full_results)

    stability_results: list[PlannerV2CaseResult] = []
    for repetition in range(1, args.repetitions + 1):
        planner = first_planner if repetition == 1 else planner_for(repetition)
        stability_results.extend(
            _run_cases(
                planner,
                stability_cases,
                variant_id=f"deepseek_prompt_v2_r{repetition}",
                model=settings.deepseek_model,
                aliases=aliases,
                progress_prefix=f"stability-r{repetition}",
            )
        )
    stability_report = _report(
        results=stability_results,
        cases=stability_cases,
        baseline_id=f"{args.baseline_id}_stability",
        dataset=args.dataset,
        retry_attempts=args.retry_attempts,
        candidates=tuple(
            f"{settings.deepseek_model}@r{repetition}"
            for repetition in range(1, args.repetitions + 1)
        ),
        notes=(
            "每次重复使用独立缓存；r1 复用同一次真实生成的全集结果。",
            "定向集包含全部 corpus verification、全部 routing boundary 和过度拆分样本 PR-016。",
        ),
    )
    _write_report(stability_report, stability_results)
    _write_comparison(
        baseline_id=args.baseline_id,
        v1_baseline=args.v1_baseline,
        full_report=full_report,
        stability_report=stability_report,
    )
    return 0


def _run_cases(
    planner: CachedResearchPlanner,
    cases: tuple[PlannerRoutingCase, ...],
    *,
    variant_id: str,
    model: str,
    aliases: tuple[str, ...],
    progress_prefix: str,
) -> list[PlannerV2CaseResult]:
    results: list[PlannerV2CaseResult] = []
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        try:
            planning = planner.plan(case.question)
        except Exception as exc:  # Evaluation failures remain in the denominator.
            result = build_planner_v2_case_result(
                variant_id=variant_id,
                model=model,
                case=case,
                corpus_aliases=aliases,
                planning=None,
                error=f"{type(exc).__name__}: {exc}",
                failure_latency_ms=round((time.perf_counter() - started) * 1000, 2),
                failure_attempts=planner.retry_attempts if isinstance(exc, ValueError) else 1,
            )
        else:
            result = build_planner_v2_case_result(
                variant_id=variant_id,
                model=model,
                case=case,
                corpus_aliases=aliases,
                planning=planning,
            )
        results.append(result)
        print(
            f"[{progress_prefix} {index}/{len(cases)}] {case.case_id}: "
            f"route={result.actual_question_type}, tasks={result.task_count}, "
            f"facets={result.task_coverage:.0%}, attempts={result.attempts}, "
            f"cache={result.cache_hit}, latency={result.generation_latency_ms:.0f}ms",
            flush=True,
        )
    return results


def _report(
    *,
    results: list[PlannerV2CaseResult],
    cases: tuple[PlannerRoutingCase, ...],
    baseline_id: str,
    dataset: Path,
    retry_attempts: int,
    candidates: tuple[str, ...],
    notes: tuple[str, ...],
) -> PlannerAblationV2Report:
    config = build_planner_ablation_v2_config(
        baseline_id=baseline_id,
        dataset_path=dataset,
        cases=cases,
        prompt_version=CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
        retry_attempts=retry_attempts,
        candidate_models=candidates,
        project_root=PROJECT_ROOT,
        notes=notes,
    )
    return build_planner_ablation_v2_report(results, config)


def _write_report(
    report: PlannerAblationV2Report,
    results: list[PlannerV2CaseResult],
) -> None:
    paths = write_planner_ablation_v2_artifacts(
        report,
        results,
        baseline_dir=PROJECT_ROOT / "evals" / "baselines",
        diagnostics_dir=PROJECT_ROOT / "evals" / "diagnostics",
    )
    print(f"Report: {paths[1]}", flush=True)


def _write_comparison(
    *,
    baseline_id: str,
    v1_baseline: Path,
    full_report: PlannerAblationV2Report,
    stability_report: PlannerAblationV2Report,
) -> None:
    baseline = json.loads(v1_baseline.read_text(encoding="utf-8"))
    baseline_variant = next(
        item for item in baseline["variants"] if item["model"] == "deepseek-v4-flash"
    )
    production_variant = next(item for item in baseline["variants"] if item["model"] == "gpt-5.5")
    candidate = full_report.variants[0]
    stable = all(item.quality_gate_passed for item in stability_report.variants)
    criteria = {
        "full_quality_gate": candidate.quality_gate_passed,
        "all_stability_repetitions_pass": stable,
        "retry_not_worse_than_deepseek_v1": (
            candidate.schema_retry_rate <= baseline_variant["schema_retry_rate"]
        ),
        "p95_faster_than_production_gpt": (
            candidate.p95_generation_latency_ms < production_variant["p95_generation_latency_ms"]
        ),
    }
    passed = all(criteria.values())
    decision = (
        "Prompt v2 通过全集 Gate 和全部定向重复，可进入生产切换评审。"
        if passed
        else "Prompt v2 未同时通过全集 Gate 和全部定向重复，生产 Planner 保持不变。"
    )
    payload = {
        "baseline_id": baseline_id,
        "baseline_source": v1_baseline.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "production_gpt_v1": production_variant,
        "baseline_deepseek_v1": baseline_variant,
        "candidate_full": candidate.model_dump(mode="json"),
        "stability_variants": [item.model_dump(mode="json") for item in stability_report.variants],
        "production_switch_criteria": criteria,
        "production_switch_review_passed": passed,
        "decision": decision,
    }
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    json_path = baseline_dir / f"{baseline_id}.json"
    markdown_path = baseline_dir / f"{baseline_id}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Planner Prompt Ablation：{baseline_id}",
        "",
        "## 全集对照",
        "",
        "| Variant | Core Route/Task/Coverage | Overall Coverage | Retry | P50/P95 | Gate |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
        _summary_row("Production GPT Prompt v1", production_variant),
        _summary_row("DeepSeek Prompt v1", baseline_variant),
        _summary_row("DeepSeek Prompt v2", candidate.model_dump(mode="json")),
        "",
        "## 定向稳定性",
        "",
        "| Repetition | Route/Task | Coverage | Retry | P50/P95 | Gate |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in stability_report.variants:
        lines.append(
            f"| {item.variant_id} | {item.acceptable_router_accuracy:.2%} / "
            f"{item.acceptable_task_count_accuracy:.2%} | {item.task_coverage:.2%} | "
            f"{item.schema_retry_rate:.2%} | {item.p50_generation_latency_ms:.0f} / "
            f"{item.p95_generation_latency_ms:.0f} ms | {item.quality_gate_passed} |"
        )
    lines.extend(
        [
            "",
            "## 决策",
            "",
            f"- Production switch review：`{passed}`",
            f"- {decision}",
            *(f"- {name}：`{value}`" for name, value in criteria.items()),
            "- 详细全集和稳定性逐题结果见同名前缀的 `_full` 与 `_stability` 报告。",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Comparison: {markdown_path}", flush=True)
    print(f"Production switch review: {passed}", flush=True)


def _summary_row(label: str, item: dict[str, object]) -> str:
    return (
        f"| {label} | {item['core_router_accuracy']:.2%} / "
        f"{item['core_task_count_accuracy']:.2%} / {item['core_task_coverage']:.2%} | "
        f"{item['task_coverage']:.2%} | {item['schema_retry_rate']:.2%} | "
        f"{item['p50_generation_latency_ms']:.0f} / "
        f"{item['p95_generation_latency_ms']:.0f} ms | {item['quality_gate_passed']} |"
    )


if __name__ == "__main__":
    raise SystemExit(main())
