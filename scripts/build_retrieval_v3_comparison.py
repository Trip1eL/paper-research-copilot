"""Build the three-way Corpus v3 retrieval comparison from saved raw results."""

import json
from collections.abc import Callable, Iterable
from statistics import median
from typing import Any, cast

from paper_research_copilot.config import PROJECT_ROOT

STRATEGIES = ("dense", "bm25", "hybrid_rrf")
DISPLAY_NAMES = {
    "dense": "Dense",
    "bm25": "BM25",
    "hybrid_rrf": "Hybrid RRF",
}
TOP_K = 10


def main() -> int:
    results = {strategy: _load_results(strategy) for strategy in STRATEGIES}
    baselines = {strategy: _load_baseline(strategy, version=3) for strategy in STRATEGIES}
    metrics = {
        strategy: {
            group: _metrics(tuple(record for record in records if filter_fn(record)))
            for group, filter_fn in _group_filters().items()
        }
        for strategy, records in results.items()
    }

    output = {
        "dataset": "evals/datasets/retrieval_discovery_v3.jsonl",
        "corpus": "agent-seed-v3",
        "collection": "agent_seed_v3_bge_m3_chunking_v1",
        "top_k": TOP_K,
        "strategies": {
            strategy: {
                "latency_p50_ms": baselines[strategy]["p50_latency_ms"],
                "groups": metrics[strategy],
                "legacy_v2_delta": _legacy_delta(strategy, metrics[strategy]["legacy_v2"]),
            }
            for strategy in STRATEGIES
        },
    }
    output_path = PROJECT_ROOT / "evals" / "baselines" / "retrieval_discovery_v3_comparison.json"
    report_path = output_path.with_suffix(".md")
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_markdown(output), encoding="utf-8")
    print(f"Comparison JSON: {output_path}")
    print(f"Comparison report: {report_path}")
    return 0


def _load_results(strategy: str) -> tuple[dict[str, Any], ...]:
    path = PROJECT_ROOT / "evals" / "results" / f"{strategy}_discovery_v3.jsonl"
    return tuple(json.loads(line) for line in path.read_text("utf-8").splitlines() if line)


def _load_baseline(strategy: str, *, version: int) -> dict[str, Any]:
    path = PROJECT_ROOT / "evals" / "baselines" / f"{strategy}_discovery_v{version}.json"
    return cast(dict[str, Any], json.loads(path.read_text("utf-8")))


def _group_filters() -> dict[str, Callable[[dict[str, Any]], bool]]:
    return {
        "all": lambda record: True,
        "legacy_v2": lambda record: _case_number(record) <= 50,
        "new_v3": lambda record: _case_number(record) > 50,
        "new_single": lambda record: 51 <= _case_number(record) <= 80,
        "new_cross": lambda record: _case_number(record) >= 81,
    }


def _case_number(record: dict[str, Any]) -> int:
    return int(record["case_id"].partition("-")[2])


def _metrics(records: tuple[dict[str, Any], ...]) -> dict[str, int | float]:
    return {
        "case_count": len(records),
        "paper_recall": _mean(_paper_recall(record) for record in records),
        "complete_papers": _mean(float(_paper_recall(record) == 1) for record in records),
        "exact_page_recall": _mean(_page_recall(record) for record in records),
        "complete_pages": _mean(float(_page_recall(record) == 1) for record in records),
        "paper_mrr": _mean(_reciprocal_rank(record, exact_page=False) for record in records),
        "page_mrr": _mean(_reciprocal_rank(record, exact_page=True) for record in records),
        "same_page_redundancy": _mean(_redundancy(record) for record in records),
        "latency_p50_ms": round(median(record["latency_ms"] for record in records), 2),
    }


def _paper_recall(record: dict[str, Any]) -> float:
    relevant = {item["paper_id"] for item in record["relevant"]}
    retrieved = {
        item["paper_id"] for item in record["candidates"][:TOP_K] if item["paper_id"]
    }
    return len(relevant & retrieved) / len(relevant)


def _page_recall(record: dict[str, Any]) -> float:
    candidates = record["candidates"][:TOP_K]
    covered = sum(
        any(
            candidate["paper_id"] == relevant["paper_id"]
            and candidate["page_number"] in relevant["pages"]
            for candidate in candidates
        )
        for relevant in record["relevant"]
    )
    return covered / len(record["relevant"])


def _reciprocal_rank(record: dict[str, Any], *, exact_page: bool) -> float:
    for candidate in record["candidates"][:TOP_K]:
        for relevant in record["relevant"]:
            if candidate["paper_id"] != relevant["paper_id"]:
                continue
            if not exact_page or candidate["page_number"] in relevant["pages"]:
                return 1 / int(candidate["rank"])
    return 0.0


def _redundancy(record: dict[str, Any]) -> float:
    candidates = record["candidates"][:TOP_K]
    if not candidates:
        return 0.0
    unique_pages = {(item["paper_id"], item["page_number"]) for item in candidates}
    return 1 - len(unique_pages) / len(candidates)


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return round(sum(materialized) / len(materialized), 4)


def _legacy_delta(strategy: str, v3_legacy: dict[str, int | float]) -> dict[str, float]:
    v2 = _load_baseline(strategy, version=2)["overall"]
    v2_top_k = v2["cutoffs"][str(TOP_K)]
    return {
        "paper_recall": round(float(v3_legacy["paper_recall"]) - v2_top_k["paper_recall"], 4),
        "complete_papers": round(
            float(v3_legacy["complete_papers"])
            - v2_top_k["complete_paper_coverage_rate"],
            4,
        ),
        "exact_page_recall": round(
            float(v3_legacy["exact_page_recall"]) - v2_top_k["exact_page_recall"],
            4,
        ),
        "paper_mrr": round(float(v3_legacy["paper_mrr"]) - v2["paper_mrr"], 4),
        "page_mrr": round(float(v3_legacy["page_mrr"]) - v2["exact_page_mrr"], 4),
    }


def _markdown(output: dict[str, Any]) -> str:
    strategies = output["strategies"]
    lines = [
        "# Corpus v3 Retriever 对照",
        "",
        "## 实验设置",
        "",
        "- Dataset：`evals/datasets/retrieval_discovery_v3.jsonl`（100 cases）",
        "- Corpus：`agent-seed-v3`，40 篇、1,387 页、2,152 Chunks",
        "- Collection：`agent_seed_v3_bge_m3_chunking_v1`",
        "- Dense Embedding：`BAAI/bge-m3`；Hybrid 使用 Dense + BM25 + RRF",
        "- Top-K：10；本报告只使用已保存结果，不调用 LLM 或 Embedding API",
        "",
        "## 总体结果",
        "",
        "| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | "
        "Paper MRR | Page MRR | Redundancy | P50 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy in STRATEGIES:
        item = strategies[strategy]
        metrics = item["groups"]["all"]
        lines.append(_table_row(DISPLAY_NAMES[strategy], metrics))

    lines.extend(["", "## 分组结果", ""])
    for group, description in (
        ("legacy_v2", "旧 50 题（DS-001..050）"),
        ("new_v3", "新增 50 题（DS-051..100）"),
        ("new_single", "新增单论文题（DS-051..080）"),
        ("new_cross", "新增跨论文题（DS-081..100）"),
    ):
        lines.extend(
            [
                f"### {description}",
                "",
                "| Strategy | Paper Recall | Complete Papers | Exact Page Recall | "
                "Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for strategy in STRATEGIES:
            lines.append(_table_row(DISPLAY_NAMES[strategy], strategies[strategy]["groups"][group]))
        lines.append("")

    lines.extend(
        [
            "## 扩库漂移",
            "",
            "同一批 DS-001..050 在 v2（20 篇）和 v3（40 篇）中的 Top-10 指标差值：",
            "",
            "| Strategy | Paper Recall | Complete Papers | Exact Page Recall | "
            "Paper MRR | Page MRR |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for strategy in STRATEGIES:
        delta = strategies[strategy]["legacy_v2_delta"]
        lines.append(
            f"| {DISPLAY_NAMES[strategy]} | {_delta(delta['paper_recall'])} | "
            f"{_delta(delta['complete_papers'])} | {_delta(delta['exact_page_recall'])} | "
            f"{delta['paper_mrr']:+.4f} | {delta['page_mrr']:+.4f} |"
        )

    dense = strategies["dense"]["groups"]["all"]
    hybrid = strategies["hybrid_rrf"]["groups"]["all"]
    hybrid_cross = strategies["hybrid_rrf"]["groups"]["new_cross"]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- Hybrid RRF 的总体 Paper Recall@10 为 {hybrid['paper_recall']:.2%}，与 Dense 的 "
            f"{dense['paper_recall']:.2%} 基本持平；Exact Page Recall@10 从 "
            f"{dense['exact_page_recall']:.2%} 提升到 {hybrid['exact_page_recall']:.2%}。",
            "- BM25 在中文问题、英文正文的跨语言设置下经常没有有效词项匹配，不适合作为独立默认 "
            "Retriever；其价值是为 Hybrid 补充公式名、指标名和精确术语。",
            f"- 新增跨论文题上 Hybrid Complete Papers@10 仅为 "
            f"{hybrid_cross['complete_papers']:.2%}，说明全局 Hybrid 仍会被一个子主题占满；"
            "这支持 Agent Runtime 对跨论文任务继续使用 Query Decomposition + Coverage Merge。",
            "- 因此 v3 不触发新的参数微调：单论文 Discovery 保持 Hybrid RRF，跨论文保持 "
            "Coverage-aware Retrieval。",
            "",
        ]
    )
    return "\n".join(lines)


def _table_row(label: str, metrics: dict[str, int | float]) -> str:
    return (
        f"| {label} | {metrics['paper_recall']:.2%} | {metrics['complete_papers']:.2%} | "
        f"{metrics['exact_page_recall']:.2%} | {metrics['complete_pages']:.2%} | "
        f"{metrics['paper_mrr']:.4f} | {metrics['page_mrr']:.4f} | "
        f"{metrics['same_page_redundancy']:.2%} | {metrics['latency_p50_ms']:.2f} ms |"
    )


def _delta(value: float) -> str:
    return f"{value:+.2%}"


if __name__ == "__main__":
    raise SystemExit(main())
