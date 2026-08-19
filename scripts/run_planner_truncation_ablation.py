"""Compare Planner truncation-recovery strategies on retry-prone Cases."""

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from paper_research_copilot.agent import (
    CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
    CachedResearchPlanner,
    PlannerAttemptTrace,
    PlannerRetryMode,
)
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import (
    build_planner_v2_case_result,
    load_planner_routing_cases,
)
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider

DEFAULT_CASE_IDS = ("PR-030", "PR-033", "PR-039")
DEFAULT_STRATEGY_IDS = ("same_1800", "compact_1800", "same_2400")


@dataclass(frozen=True)
class Strategy:
    strategy_id: str
    max_tokens: int
    retry_mode: PlannerRetryMode
    complexity_rank: int


STRATEGIES = (
    Strategy("same_1800", 1800, "same_prompt", 0),
    Strategy("compact_1800", 1800, "compact_json", 1),
    Strategy("same_2400", 2400, "same_prompt", 0),
    Strategy("compact_2400", 2400, "compact_json", 1),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "planner_routing_v2.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--strategy",
        action="append",
        choices=tuple(strategy.strategy_id for strategy in STRATEGIES),
        default=[],
    )
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--baseline-id", default="planner_truncation_recovery_v1")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data" / "agent")
    args = parser.parse_args()
    if args.repetitions < 1:
        raise ValueError("Planner truncation ablation requires at least one repetition")
    if args.retry_attempts < 1:
        raise ValueError("Planner retry attempts must be positive")
    selected_strategy_ids = tuple(
        dict.fromkeys(args.strategy or DEFAULT_STRATEGY_IDS)
    )
    strategies_by_id = {strategy.strategy_id: strategy for strategy in STRATEGIES}
    selected_strategies = tuple(
        strategies_by_id[strategy_id] for strategy_id in selected_strategy_ids
    )

    all_cases = load_planner_routing_cases(args.dataset)
    cases_by_id = {case.case_id: case for case in all_cases}
    selected_ids = tuple(args.case_id or DEFAULT_CASE_IDS)
    unknown = sorted(set(selected_ids) - cases_by_id.keys())
    if unknown:
        raise ValueError(f"Unknown Planner truncation Case IDs: {unknown}")
    cases = tuple(cases_by_id[case_id] for case_id in selected_ids)

    settings = get_settings()
    llm_url, llm_key = settings.require_llm_credentials()
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    aliases = tuple(
        alias
        for asset in catalog.papers
        for alias in (asset.spec.slug, asset.spec.title, asset.spec.title.partition(":")[0])
    )
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.deepseek_model)
    raw_path = args.cache_dir / f"{args.baseline_id}_raw.jsonl"
    raw_records: list[dict[str, object]] = []
    diagnostics: list[dict[str, Any]] = []

    # Interleaving reduces the risk that one strategy receives a uniquely quiet provider window.
    for repetition in range(1, args.repetitions + 1):
        for case in cases:
            for strategy in selected_strategies:
                planner = CachedResearchPlanner(
                    OpenAICompatibleChatProvider(
                        base_url=llm_url,
                        api_key=llm_key,
                        model=settings.deepseek_model,
                        max_tokens=strategy.max_tokens,
                    ),
                    model=settings.deepseek_model,
                    cache_path=args.cache_dir
                    / (
                        f"{args.baseline_id}_{safe_model}_{strategy.strategy_id}"
                        f"_r{repetition}.jsonl"
                    ),
                    forbidden_aliases=aliases,
                    retry_attempts=args.retry_attempts,
                    prompt_version=CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
                    retry_mode=strategy.retry_mode,
                )
                started = time.perf_counter()
                planning = None
                error: str | None = None
                try:
                    planning = planner.plan(case.question)
                except Exception as exc:  # Keep terminal failures in every metric denominator.
                    error = f"{type(exc).__name__}: {exc}"
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                trace = planner.trace_for(case.question)
                failure_attempts = len(trace.attempts)
                evaluation = build_planner_v2_case_result(
                    variant_id=strategy.strategy_id,
                    model=settings.deepseek_model,
                    case=case,
                    corpus_aliases=aliases,
                    planning=planning,
                    error=error,
                    failure_latency_ms=elapsed_ms,
                    failure_attempts=failure_attempts,
                )
                raw_records.append(
                    {
                        "strategy_id": strategy.strategy_id,
                        "repetition": repetition,
                        "case_id": case.case_id,
                        "trace": trace.model_dump(mode="json"),
                    }
                )
                _write_raw_records(raw_path, raw_records)
                diagnostics.append(
                    {
                        "strategy_id": strategy.strategy_id,
                        "max_tokens": strategy.max_tokens,
                        "retry_mode": strategy.retry_mode,
                        "repetition": repetition,
                        "case_id": case.case_id,
                        "success": evaluation.success,
                        "error": evaluation.error,
                        "cache_hit": evaluation.cache_hit,
                        "route": evaluation.actual_question_type,
                        "strict_route": evaluation.strict_router_correct,
                        "acceptable_route": evaluation.acceptable_router_correct,
                        "task_count": evaluation.task_count,
                        "strict_task_count": evaluation.strict_task_count_correct,
                        "acceptable_task_count": evaluation.acceptable_task_count_correct,
                        "covered_facets": list(evaluation.covered_facets),
                        "facet_coverage": evaluation.task_coverage,
                        "title_leaks": list(evaluation.title_leaks),
                        "generation_latency_ms": evaluation.generation_latency_ms,
                        "attempt_count": len(trace.attempts),
                        "retry_recovered": trace.retry_recovered,
                        "attempts": [_sanitize_attempt(attempt) for attempt in trace.attempts],
                        "plan": (
                            evaluation.plan.model_dump(mode="json")
                            if evaluation.plan is not None
                            else None
                        ),
                    }
                )
                outcomes = " -> ".join(attempt.outcome for attempt in trace.attempts)
                usage = _trace_usage(trace.attempts)
                print(
                    f"[r{repetition} {case.case_id} {strategy.strategy_id}] "
                    f"{outcomes}; attempts={len(trace.attempts)}, "
                    f"latency={evaluation.generation_latency_ms:.0f}ms, "
                    f"tokens={usage['total_tokens']}, cache={evaluation.cache_hit}",
                    flush=True,
                )

    summaries = [
        _summarize_strategy(
            strategy,
            [item for item in diagnostics if item["strategy_id"] == strategy.strategy_id],
        )
        for strategy in selected_strategies
    ]
    recommended, recommendation_reason = _recommend(summaries)
    report = {
        "baseline_id": args.baseline_id,
        "evaluated_on": date.today().isoformat(),
        "model": settings.deepseek_model,
        "prompt_version": CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
        "dataset_path": args.dataset.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "case_ids": list(selected_ids),
        "repetitions": args.repetitions,
        "run_count": len(diagnostics),
        "retry_attempts": args.retry_attempts,
        "strategy_ids": list(selected_strategy_ids),
        "execution_order": "repetition -> case -> strategy",
        "quality_gate": (
            "success=100%; acceptable_route=100%; acceptable_task_count=100%; "
            "facet_coverage=100%; title_leakage=0%"
        ),
        "raw_trace_path": raw_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "raw_trace_versioned": False,
        "strategies": summaries,
        "recommended_strategy": recommended,
        "recommendation_reason": recommendation_reason,
        "production_default_changed": False,
    }
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    diagnostics_dir = PROJECT_ROOT / "evals" / "diagnostics"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{args.baseline_id}.json"
    markdown_path = baseline_dir / f"{args.baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{args.baseline_id}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown_path.write_text(_markdown(report, diagnostics), encoding="utf-8")
    print(f"Summary: {markdown_path}")
    print(f"Diagnostics: {diagnostics_path}")
    print(f"Raw ignored trace: {raw_path}")
    print(f"Recommended strategy: {recommended or 'none'}")
    return 0


def _sanitize_attempt(attempt: PlannerAttemptTrace) -> dict[str, object]:
    payload = attempt.model_dump(mode="json", exclude={"raw_response"})
    payload["raw_response_sha256"] = hashlib.sha256(
        attempt.raw_response.encode("utf-8")
    ).hexdigest()
    return payload


def _write_raw_records(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    path.write_text(content + "\n", encoding="utf-8")


def _summarize_strategy(
    strategy: Strategy,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    if not records:
        raise ValueError(f"Strategy {strategy.strategy_id} has no records")
    attempts = [attempt for record in records for attempt in record["attempts"]]
    retry_records = [record for record in records if int(record["attempt_count"]) > 1]
    latencies = sorted(float(record["generation_latency_ms"]) for record in records)
    usage = _attempt_dict_usage(attempts)
    summary = {
        "strategy_id": strategy.strategy_id,
        "max_tokens": strategy.max_tokens,
        "retry_mode": strategy.retry_mode,
        "run_count": len(records),
        "success_rate": _mean(bool(record["success"]) for record in records),
        "strict_route_accuracy": _mean(bool(record["strict_route"]) for record in records),
        "acceptable_route_accuracy": _mean(bool(record["acceptable_route"]) for record in records),
        "strict_task_count_accuracy": _mean(
            bool(record["strict_task_count"]) for record in records
        ),
        "acceptable_task_count_accuracy": _mean(
            bool(record["acceptable_task_count"]) for record in records
        ),
        "facet_coverage": sum(float(record["facet_coverage"]) for record in records) / len(records),
        "title_leakage_rate": _mean(bool(record["title_leaks"]) for record in records),
        "retry_rate": len(retry_records) / len(records),
        "retry_recovery_rate": (
            _mean(bool(record["retry_recovered"]) for record in retry_records)
            if retry_records
            else None
        ),
        "truncated_attempt_count": sum(attempt["outcome"] == "truncated" for attempt in attempts),
        "outcome_counts": dict(Counter(attempt["outcome"] for attempt in attempts)),
        "p50_generation_latency_ms": _percentile(latencies, 0.50),
        "p95_generation_latency_ms": _percentile(latencies, 0.95),
        "attempt_count": len(attempts),
        "model_call_count": len(attempts),
        "cache_hit_count": sum(bool(record["cache_hit"]) for record in records),
        **usage,
    }
    summary["quality_gate_passed"] = bool(
        summary["success_rate"] == 1
        and summary["acceptable_route_accuracy"] == 1
        and summary["acceptable_task_count_accuracy"] == 1
        and summary["facet_coverage"] == 1
        and summary["title_leakage_rate"] == 0
    )
    summary["complexity_rank"] = strategy.complexity_rank
    return summary


def _recommend(summaries: list[dict[str, Any]]) -> tuple[str | None, str]:
    passing = [summary for summary in summaries if summary["quality_gate_passed"]]
    if not passing:
        return None, "没有策略通过全部质量门槛；保留当前生产配置，不继续进行同类 Prompt 微调。"
    recommended = min(
        passing,
        key=lambda item: (
            item["retry_rate"],
            item["p95_generation_latency_ms"],
            item["total_output_tokens"],
            item["complexity_rank"],
        ),
    )
    return (
        str(recommended["strategy_id"]),
        f"{recommended['strategy_id']} 通过质量门槛，并按 Retry Rate、P95、"
        "Output Tokens、实现复杂度的顺序取得最优排序。",
    )


def _trace_usage(attempts: tuple[PlannerAttemptTrace, ...]) -> dict[str, int]:
    return {
        "input_tokens": sum(attempt.usage.input_tokens or 0 for attempt in attempts),
        "output_tokens": sum(attempt.usage.output_tokens or 0 for attempt in attempts),
        "total_tokens": sum(attempt.usage.total_tokens or 0 for attempt in attempts),
    }


def _attempt_dict_usage(attempts: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_input_tokens": sum(attempt["usage"]["input_tokens"] or 0 for attempt in attempts),
        "total_output_tokens": sum(attempt["usage"]["output_tokens"] or 0 for attempt in attempts),
        "total_tokens": sum(attempt["usage"]["total_tokens"] or 0 for attempt in attempts),
    }


def _mean(values: Any) -> float:
    materialized = tuple(values)
    return sum(float(value) for value in materialized) / len(materialized)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    return round(values[max(0, round((len(values) - 1) * percentile))], 2)


def _markdown(report: dict[str, Any], diagnostics: list[dict[str, Any]]) -> str:
    lines = [
        f"# Planner Truncation Recovery Ablation：{report['baseline_id']}",
        "",
        f"- Model：`{report['model']}`",
        f"- Prompt：`{report['prompt_version']}`",
        f"- Cases：{', '.join(report['case_ids'])}",
        f"- Repetitions：{report['repetitions']}（共 {report['run_count']} Plans）",
        f"- Raw trace：`{report['raw_trace_path']}`（ignored，不进入 Git）",
        "",
        "## 汇总",
        "",
        "| Strategy | Quality | Success | Route S/A | Tasks S/A | Facets | Leakage | "
        "Retry / Recovery | Truncated | P50 / P95 | Calls | Output Tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["strategies"]:
        recovery = (
            "N/A" if item["retry_recovery_rate"] is None else f"{item['retry_recovery_rate']:.2%}"
        )
        lines.append(
            f"| {item['strategy_id']} | {item['quality_gate_passed']} | "
            f"{item['success_rate']:.2%} | {item['strict_route_accuracy']:.2%} / "
            f"{item['acceptable_route_accuracy']:.2%} | "
            f"{item['strict_task_count_accuracy']:.2%} / "
            f"{item['acceptable_task_count_accuracy']:.2%} | "
            f"{item['facet_coverage']:.2%} | {item['title_leakage_rate']:.2%} | "
            f"{item['retry_rate']:.2%} / {recovery} | "
            f"{item['truncated_attempt_count']} | "
            f"{item['p50_generation_latency_ms']:.0f} / "
            f"{item['p95_generation_latency_ms']:.0f} ms | "
            f"{item['model_call_count']} | {item['total_output_tokens']} |"
        )
    lines.extend(
        [
            "",
            "## 推荐",
            "",
            f"- Strategy：`{report['recommended_strategy'] or 'none'}`",
            f"- Reason：{report['recommendation_reason']}",
            "- 本实验未自动修改生产默认配置。",
            "",
            "## 逐次结果",
            "",
            "| Rep | Case | Strategy | Success | Route | Tasks | Facets | Outcomes | "
            "Latency | Tokens |",
            "| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
        ]
    )
    for item in diagnostics:
        outcomes = " -> ".join(attempt["outcome"] for attempt in item["attempts"])
        tokens = sum(attempt["usage"]["total_tokens"] or 0 for attempt in item["attempts"])
        lines.append(
            f"| {item['repetition']} | {item['case_id']} | {item['strategy_id']} | "
            f"{item['success']} | {item['route']} | {item['task_count']} | "
            f"{item['facet_coverage']:.0%} | {outcomes} | "
            f"{item['generation_latency_ms']:.0f} ms | {tokens} |"
        )
    lines.extend(
        [
            "",
            "正式 Diagnostics 不包含 `raw_response`，只保留 SHA256、长度、错误、成本和"
            "结构化 Plan；原始响应只保存在 ignored 路径。",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
