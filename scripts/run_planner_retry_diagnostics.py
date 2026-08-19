"""Diagnose Planner retry causes with attempt-level traces."""

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path

from paper_research_copilot.agent import (
    CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
    CachedResearchPlanner,
    PlannerAttemptTrace,
)
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import load_planner_routing_cases
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider

DEFAULT_CASE_IDS = ("PR-030", "PR-033", "PR-039")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "planner_routing_v2.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--baseline-id", default="planner_retry_diagnostics_v1")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / "data" / "agent")
    args = parser.parse_args()
    if args.repetitions < 1:
        raise ValueError("Planner retry diagnostics requires at least one repetition")
    if args.retry_attempts < 1:
        raise ValueError("Planner retry attempts must be positive")

    all_cases = load_planner_routing_cases(args.dataset)
    cases_by_id = {case.case_id: case for case in all_cases}
    selected_ids = tuple(args.case_id or DEFAULT_CASE_IDS)
    unknown = sorted(set(selected_ids) - cases_by_id.keys())
    if unknown:
        raise ValueError(f"Unknown Planner retry diagnostic Case IDs: {unknown}")
    cases = tuple(cases_by_id[case_id] for case_id in selected_ids)

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
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.deepseek_model)
    raw_path = args.cache_dir / f"{args.baseline_id}_raw.jsonl"
    raw_records: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []

    for repetition in range(1, args.repetitions + 1):
        planner = CachedResearchPlanner(
            OpenAICompatibleChatProvider(
                base_url=llm_url,
                api_key=llm_key,
                model=settings.deepseek_model,
                max_tokens=settings.agent_planner_max_tokens,
            ),
            model=settings.deepseek_model,
            cache_path=args.cache_dir / f"{args.baseline_id}_{safe_model}_r{repetition}.jsonl",
            forbidden_aliases=aliases,
            retry_attempts=args.retry_attempts,
            prompt_version=CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
        )
        for index, case in enumerate(cases, start=1):
            started = time.perf_counter()
            error: str | None = None
            plan: dict[str, object] | None = None
            cache_hit = False
            try:
                planning = planner.plan(case.question)
            except Exception as exc:  # Diagnostics retain terminal failures.
                generation_latency_ms = round((time.perf_counter() - started) * 1000, 2)
                error = f"{type(exc).__name__}: {exc}"
            else:
                generation_latency_ms = planning.generation_latency_ms
                cache_hit = planning.cache_hit
                plan = planning.plan.model_dump(mode="json")
            trace = planner.trace_for(case.question)
            raw_records.append(
                {
                    "repetition": repetition,
                    "case_id": case.case_id,
                    "trace": trace.model_dump(mode="json"),
                }
            )
            _write_raw_records(raw_path, raw_records)
            diagnostics.append(
                {
                    "repetition": repetition,
                    "case_id": case.case_id,
                    "category": case.category,
                    "success": error is None,
                    "error": error,
                    "cache_hit": cache_hit,
                    "generation_latency_ms": generation_latency_ms,
                    "attempt_count": len(trace.attempts),
                    "retry_recovered": trace.retry_recovered,
                    "final_outcome": trace.final_outcome,
                    "attempts": [_sanitize_attempt(item) for item in trace.attempts],
                    "plan": plan,
                }
            )
            print(
                f"[r{repetition} {index}/{len(cases)}] {case.case_id}: "
                f"outcomes={[item.outcome for item in trace.attempts]}, "
                f"latency={generation_latency_ms:.0f}ms, cache={cache_hit}",
                flush=True,
            )

    summary = _build_summary(
        baseline_id=args.baseline_id,
        model=settings.deepseek_model,
        dataset=args.dataset,
        case_ids=selected_ids,
        repetitions=args.repetitions,
        retry_attempts=args.retry_attempts,
        planner_max_tokens=settings.agent_planner_max_tokens,
        diagnostics=diagnostics,
        raw_path=raw_path,
    )
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    diagnostics_dir = PROJECT_ROOT / "evals" / "diagnostics"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{args.baseline_id}.json"
    markdown_path = baseline_dir / f"{args.baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{args.baseline_id}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    diagnostics_path.write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        _markdown(summary, diagnostics),
        encoding="utf-8",
    )
    print(f"Summary: {markdown_path}")
    print(f"Diagnostics: {diagnostics_path}")
    print(f"Raw ignored trace: {raw_path}")
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


def _build_summary(
    *,
    baseline_id: str,
    model: str,
    dataset: Path,
    case_ids: tuple[str, ...],
    repetitions: int,
    retry_attempts: int,
    planner_max_tokens: int,
    diagnostics: list[dict[str, object]],
    raw_path: Path,
) -> dict[str, object]:
    attempts = [attempt for item in diagnostics for attempt in item["attempts"]]
    outcome_counts = Counter(attempt["outcome"] for attempt in attempts)
    finish_reason_counts = Counter(attempt["finish_reason"] for attempt in attempts)
    failure_outcomes = Counter(
        attempt["outcome"] for attempt in attempts if attempt["outcome"] != "accepted"
    )
    latencies = sorted(float(item["generation_latency_ms"]) for item in diagnostics)
    retry_count = sum(int(item["attempt_count"]) > 1 for item in diagnostics)
    recovery_count = sum(bool(item["retry_recovered"]) for item in diagnostics)
    truncated_attempts = [attempt for attempt in attempts if attempt["outcome"] == "truncated"]
    output_limit_hits = sum(
        attempt["usage"]["output_tokens"] == planner_max_tokens for attempt in truncated_attempts
    )
    empty_truncated = sum(int(attempt["content_length"]) == 0 for attempt in truncated_attempts)
    return {
        "baseline_id": baseline_id,
        "evaluated_on": date.today().isoformat(),
        "model": model,
        "prompt_version": CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
        "dataset_path": dataset.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "case_ids": list(case_ids),
        "repetitions": repetitions,
        "run_count": len(diagnostics),
        "retry_attempts": retry_attempts,
        "planner_max_tokens": planner_max_tokens,
        "success_rate": sum(bool(item["success"]) for item in diagnostics) / len(diagnostics),
        "retry_rate": retry_count / len(diagnostics),
        "retry_recovery_rate": recovery_count / retry_count if retry_count else None,
        "outcome_counts": dict(outcome_counts),
        "failure_outcome_counts": dict(failure_outcomes),
        "finish_reason_counts": dict(finish_reason_counts),
        "output_token_limit_hit_count": output_limit_hits,
        "empty_truncated_response_count": empty_truncated,
        "p50_generation_latency_ms": _percentile(latencies, 0.50),
        "p95_generation_latency_ms": _percentile(latencies, 0.95),
        "raw_trace_path": raw_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
        "raw_trace_versioned": False,
        "diagnosis": _diagnosis(
            failure_outcomes,
            truncated_count=len(truncated_attempts),
            output_limit_hits=output_limit_hits,
            empty_truncated=empty_truncated,
            planner_max_tokens=planner_max_tokens,
        ),
    }


def _diagnosis(
    failures: Counter[object],
    *,
    truncated_count: int,
    output_limit_hits: int,
    empty_truncated: int,
    planner_max_tokens: int,
) -> str:
    if not failures:
        return "本次独立复跑没有触发重试，无法从新样本确定历史重试根因。"
    ordered = ", ".join(f"{outcome}={count}" for outcome, count in failures.most_common())
    detail = (
        f"其中 {output_limit_hits}/{truncated_count} 个截断 attempt 的 output_tokens "
        f"达到配置上限 {planner_max_tokens}，{empty_truncated} 个返回空 content。"
        if truncated_count
        else ""
    )
    return f"观察到的 Planner 重试触发类型：{ordered}。{detail}"


def _markdown(
    summary: dict[str, object],
    diagnostics: list[dict[str, object]],
) -> str:
    lines = [
        f"# Planner Retry Diagnostics：{summary['baseline_id']}",
        "",
        f"- Model：`{summary['model']}`",
        f"- Prompt：`{summary['prompt_version']}`",
        f"- Cases：{', '.join(summary['case_ids'])}",
        f"- Repetitions：{summary['repetitions']}",
        f"- Raw trace：`{summary['raw_trace_path']}`（ignored，不进入 Git）",
        "",
        "## 汇总",
        "",
        f"- Success：{summary['success_rate']:.2%}",
        f"- Retry Rate：{summary['retry_rate']:.2%}",
        f"- Retry Recovery：{_rate(summary['retry_recovery_rate'])}",
        f"- Outcomes：`{summary['outcome_counts']}`",
        f"- Finish reasons：`{summary['finish_reason_counts']}`",
        f"- Max tokens：{summary['planner_max_tokens']}",
        f"- Output-limit hits：{summary['output_token_limit_hit_count']}",
        f"- Empty truncated responses：{summary['empty_truncated_response_count']}",
        f"- P50/P95：{summary['p50_generation_latency_ms']:.0f} / "
        f"{summary['p95_generation_latency_ms']:.0f} ms",
        f"- Diagnosis：{summary['diagnosis']}",
        "",
        "## 逐次结果",
        "",
        "| Rep | Case | Success | Attempts | Outcomes | Latency |",
        "| ---: | --- | --- | ---: | --- | ---: |",
    ]
    for item in diagnostics:
        outcomes = " -> ".join(attempt["outcome"] for attempt in item["attempts"])
        lines.append(
            f"| {item['repetition']} | {item['case_id']} | {item['success']} | "
            f"{item['attempt_count']} | {outcomes} | "
            f"{item['generation_latency_ms']:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "正式 Diagnostics 不包含 `raw_response`，仅包含响应 SHA256、长度、错误和成本；"
            "原始响应只保存在 ignored 路径。",
        ]
    )
    return "\n".join(lines) + "\n"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    return values[max(0, round((len(values) - 1) * percentile))]


def _rate(value: object) -> str:
    return "N/A" if value is None else f"{float(value):.2%}"


if __name__ == "__main__":
    raise SystemExit(main())
