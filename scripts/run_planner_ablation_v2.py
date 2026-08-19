"""Run the 40-case Planner/Router model ablation v2."""

import argparse
import re
import time
from pathlib import Path

from paper_research_copilot.agent import (
    RESEARCH_PLANNER_PROMPT_VERSION,
    CachedResearchPlanner,
)
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import (
    PlannerV2CaseResult,
    build_planner_ablation_v2_config,
    build_planner_ablation_v2_report,
    build_planner_v2_case_result,
    load_planner_routing_cases,
    write_planner_ablation_v2_artifacts,
)
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "planner_routing_v2.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--baseline-id", default="planner_model_ablation_v2")
    parser.add_argument("--gpt-cache", type=Path)
    parser.add_argument("--deepseek-cache", type=Path)
    args = parser.parse_args()
    if args.retry_attempts < 1:
        raise ValueError("Planner retry attempts must be positive")

    all_cases = load_planner_routing_cases(args.dataset)
    if args.case_id:
        cases_by_id = {case.case_id: case for case in all_cases}
        unknown = sorted(set(args.case_id) - cases_by_id.keys())
        if unknown:
            raise ValueError(f"Unknown Planner v2 Case IDs: {unknown}")
        cases = tuple(cases_by_id[case_id] for case_id in args.case_id)
    else:
        cases = all_cases

    settings = get_settings()
    relay_url, relay_key = settings.require_relay_credentials()
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
    planners = (
        (
            "gpt_5_5",
            settings.gpt_model_name,
            CachedResearchPlanner(
                OpenAICompatibleChatProvider(
                    base_url=relay_url,
                    api_key=relay_key,
                    model=settings.gpt_model_name,
                    max_tokens=settings.agent_planner_max_tokens,
                ),
                model=settings.gpt_model_name,
                cache_path=args.gpt_cache or _default_cache_path(settings.gpt_model_name),
                forbidden_aliases=aliases,
                retry_attempts=args.retry_attempts,
            ),
        ),
        (
            "deepseek_v4_flash",
            settings.deepseek_model,
            CachedResearchPlanner(
                OpenAICompatibleChatProvider(
                    base_url=llm_url,
                    api_key=llm_key,
                    model=settings.deepseek_model,
                    max_tokens=settings.agent_planner_max_tokens,
                ),
                model=settings.deepseek_model,
                cache_path=args.deepseek_cache or _default_cache_path(settings.deepseek_model),
                forbidden_aliases=aliases,
                retry_attempts=args.retry_attempts,
            ),
        ),
    )

    results: list[PlannerV2CaseResult] = []
    for variant_id, model, planner in planners:
        for index, case in enumerate(cases, start=1):
            started = time.perf_counter()
            try:
                planning = planner.plan(case.question)
            except Exception as exc:  # Keep failures in the evaluation denominator.
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                failure_attempts = args.retry_attempts if isinstance(exc, ValueError) else 1
                result = build_planner_v2_case_result(
                    variant_id=variant_id,
                    model=model,
                    case=case,
                    corpus_aliases=aliases,
                    planning=None,
                    error=f"{type(exc).__name__}: {exc}",
                    failure_latency_ms=elapsed_ms,
                    failure_attempts=failure_attempts,
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
                f"[{model} {index}/{len(cases)}] {case.case_id}: "
                f"success={result.success}, cache={result.cache_hit}, "
                f"route={result.actual_question_type}, tasks={result.task_count}, "
                f"facets={result.task_coverage:.0%}, attempts={result.attempts}, "
                f"latency={result.generation_latency_ms:.0f}ms",
                flush=True,
            )

    config = build_planner_ablation_v2_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        cases=cases,
        prompt_version=RESEARCH_PLANNER_PROMPT_VERSION,
        retry_attempts=args.retry_attempts,
        candidate_models=tuple(model for _, model, _ in planners),
        project_root=PROJECT_ROOT,
        notes=(
            "两组使用相同的 system/user Prompt、max_tokens、Pydantic Schema、重试策略和 "
            "Corpus alias 泄漏审计。",
            "Strict 指标遵循唯一金标；Acceptable 指标允许人工标注的合理替代；Core 指标排除 "
            "label-sensitive Cases。",
            "Route 和 Task Count 可采用 Acceptable 标注，但所有 Case 的证据 Facet Coverage "
            "仍须为 100%。",
            "缓存命中时读取原始 generation latency；Provider 负载随时间变化，延迟仅用于"
            "方向性对比。",
        ),
    )
    report = build_planner_ablation_v2_report(results, config)
    json_path, markdown_path, diagnostics_path = write_planner_ablation_v2_artifacts(
        report,
        results,
        baseline_dir=PROJECT_ROOT / "evals" / "baselines",
        diagnostics_dir=PROJECT_ROOT / "evals" / "diagnostics",
    )
    print(f"Baseline JSON: {json_path}")
    print(f"Baseline report: {markdown_path}")
    print(f"Diagnostics: {diagnostics_path}")
    print(f"Recommended Planner: {report.recommended_model or 'none'}")
    return 0


def _default_cache_path(model: str) -> Path:
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", model)
    return PROJECT_ROOT / "data" / "agent" / f"research_plans_v1_{safe_model}.jsonl"


if __name__ == "__main__":
    raise SystemExit(main())
