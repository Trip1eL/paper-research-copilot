"""Evaluate reranking over shared Fast and Deep Discovery candidate pools."""

import argparse
import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.evaluation import (
    RetrievalCaseResult,
    build_evaluation_config,
    build_evaluation_report,
    load_retrieval_diagnostics,
    write_evaluation_artifacts,
)
from paper_research_copilot.evaluation.datasets import RetrievalDiagnosticCase
from paper_research_copilot.evaluation.retrieval import RetrievedCandidate
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import SiliconFlowRerankerProvider
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.retrieval import (
    Bm25Retriever,
    CachedQueryRewriter,
    RerankingRetriever,
    RetrievalMode,
    find_query_rewrite_alias_leaks,
    fuse_query_rankings_max,
    fuse_rankings,
)


class _StaticCandidateRetriever:
    def __init__(self, candidates: tuple[RetrievedChunk, ...]) -> None:
        self._candidates = candidates

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self._candidates[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--collection", default="agent_seed_v2_bge_m3_chunking_v1")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "retrieval_discovery_v2.jsonl",
    )
    parser.add_argument(
        "--rewrite-cache",
        type=Path,
        default=(
            PROJECT_ROOT
            / "evals"
            / "query_rewrites"
            / "retrieval_discovery_v2_deepseek-v4-flash_query_rewrite_v1.jsonl"
        ),
    )
    parser.add_argument("--candidate-pool", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--smoke-case-id", default=None)
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines" / "reranker_ablation_v2.md",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=PROJECT_ROOT / "evals" / "diagnostics" / "reranker_ablation_v2.json",
    )
    args = parser.parse_args()
    if min(args.candidate_pool, args.rrf_k, args.top_k) < 1:
        raise ValueError("Candidate pool, RRF k, and Top-K must be positive")

    settings = get_settings()
    siliconflow_url, siliconflow_key = settings.require_siliconflow_credentials()
    reranker_provider = SiliconFlowRerankerProvider(
        siliconflow_url,
        siliconflow_key,
        settings.siliconflow_reranker_model,
    )
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    page_counts = {asset.spec.paper_id: asset.manifest.page_count for asset in catalog.papers}
    paper_aliases: dict[str, tuple[str, ...]] = {
        asset.spec.paper_id: (
            asset.spec.slug,
            asset.spec.title,
            asset.spec.title.partition(":")[0],
        )
        for asset in catalog.papers
    }
    cases = load_retrieval_diagnostics(
        args.dataset,
        allowed_paper_ids=set(page_counts),
        paper_page_counts=page_counts,
        paper_aliases=paper_aliases,
    )
    if args.smoke_case_id:
        cases = tuple(case for case in cases if case.case_id == args.smoke_case_id)
        if not cases:
            raise ValueError(f"Unknown smoke Case ID: {args.smoke_case_id}")
    rewriter = CachedQueryRewriter(
        None,
        model=settings.deepseek_model,
        cache_path=args.rewrite_cache,
        rewrite_count=3,
    )
    rewrite_records = [rewriter.record_for(case.question) for case in cases]
    leaks = find_query_rewrite_alias_leaks(
        rewrite_records,
        (alias for aliases in paper_aliases.values() for alias in aliases),
    )
    if leaks:
        raise ValueError(f"Query rewrites contain forbidden Corpus aliases: {leaks}")

    variant_ids = (
        "reranker_fast_base_v2",
        "reranker_fast_bge_v2",
        "reranker_deep_max_base_v2",
        "reranker_deep_max_bge_v2",
    )
    results: dict[str, list[RetrievalCaseResult]] = {variant_id: [] for variant_id in variant_ids}
    reranker_latencies: dict[str, list[float]] = {
        "reranker_fast_bge_v2": [],
        "reranker_deep_max_bge_v2": [],
    }
    traces: list[dict[str, Any]] = []

    runtime = build_retrieval_runtime(settings, args.collection)
    try:
        corpus_filter: dict[str, str | int | bool] = {
            "corpus_id": catalog.spec.corpus_id,
            "corpus_version": catalog.spec.version,
            "chunking_version": settings.chunking_version,
        }
        dense = runtime.retriever_for(RetrievalMode.EVIDENCE)
        bm25 = Bm25Retriever(runtime.vector_store.list_chunks(corpus_filter))
        for index, case in enumerate(cases, start=1):
            queries = (case.question, *rewriter.rewrite(case.question))
            query_groups = []
            query_latencies = []
            for query in queries:
                started = time.perf_counter()
                query_groups.append(
                    (
                        dense.retrieve(query, args.candidate_pool),
                        bm25.retrieve(query, args.candidate_pool),
                    )
                )
                query_latencies.append((time.perf_counter() - started) * 1000)
            frozen_groups = tuple(query_groups)
            fast_pool = fuse_rankings(
                frozen_groups[0],
                top_k=args.candidate_pool,
                rrf_k=args.rrf_k,
            )
            deep_pool = fuse_query_rankings_max(
                frozen_groups,
                top_k=args.candidate_pool,
                rrf_k=args.rrf_k,
            )
            fast_reranker = RerankingRetriever(
                _StaticCandidateRetriever(fast_pool),
                reranker_provider,
                candidate_pool_size=args.candidate_pool,
            )
            deep_reranker = RerankingRetriever(
                _StaticCandidateRetriever(deep_pool),
                reranker_provider,
                candidate_pool_size=args.candidate_pool,
            )
            fast_reranked = fast_reranker.retrieve(case.question, args.top_k)
            deep_reranked = deep_reranker.retrieve(case.question, args.top_k)
            fast_trace = fast_reranker.trace_for(case.question)
            deep_trace = deep_reranker.trace_for(case.question)
            reranker_latencies["reranker_fast_bge_v2"].append(fast_trace.latency_ms)
            reranker_latencies["reranker_deep_max_bge_v2"].append(deep_trace.latency_ms)
            results["reranker_fast_base_v2"].append(
                _case_result(case, fast_pool[: args.top_k], queries[:1], query_latencies[0])
            )
            results["reranker_fast_bge_v2"].append(
                _case_result(
                    case,
                    fast_reranked,
                    queries[:1],
                    query_latencies[0] + fast_trace.latency_ms,
                )
            )
            results["reranker_deep_max_base_v2"].append(
                _case_result(case, deep_pool[: args.top_k], queries, sum(query_latencies))
            )
            results["reranker_deep_max_bge_v2"].append(
                _case_result(
                    case,
                    deep_reranked,
                    queries,
                    sum(query_latencies) + deep_trace.latency_ms,
                )
            )
            traces.append(
                {
                    "case_id": case.case_id,
                    "targets": [
                        {
                            "paper_id": relevant.paper_id,
                            "relevant_pages": relevant.pages,
                            "fast": _target_trace(fast_trace, relevant.paper_id, relevant.pages),
                            "deep": _target_trace(deep_trace, relevant.paper_id, relevant.pages),
                        }
                        for relevant in case.relevant
                    ],
                }
            )
            print(
                f"[{index}/{len(cases)}] {case.case_id}: "
                f"fast_rerank={fast_trace.latency_ms:.0f}ms, "
                f"deep_rerank={deep_trace.latency_ms:.0f}ms"
            )
    finally:
        runtime.close()

    if args.smoke_case_id:
        print(f"Candidate-pool smoke test passed: {args.smoke_case_id}")
        return 0

    reports = {}
    for variant_id in variant_ids:
        uses_deep = "deep" in variant_id
        uses_reranker = variant_id.endswith("_bge_v2")
        parameters: dict[str, str | int | float | bool] = {
            "candidate_pool_size": args.candidate_pool,
            "rrf_k": args.rrf_k,
            "fusion": "max_over_query" if uses_deep else "original_query_rrf",
            "query_rewrite": uses_deep,
            "reranker": uses_reranker,
        }
        if uses_reranker:
            latencies = reranker_latencies[variant_id]
            parameters.update(
                {
                    "reranker_model": reranker_provider.model,
                    "reranker_mean_ms": round(sum(latencies) / len(latencies), 2),
                }
            )
        config = build_evaluation_config(
            baseline_id=variant_id,
            dataset_path=args.dataset,
            corpus_id=catalog.spec.corpus_id,
            corpus_version=catalog.spec.version,
            collection_name=args.collection,
            embedding_model=settings.siliconflow_embedding_model,
            chunking_version=settings.chunking_version,
            retrieval_strategy=variant_id.removesuffix("_v2"),
            strategy_parameters=parameters,
            top_k=args.top_k,
            cutoffs=(1, 3, 5, args.top_k),
            project_root=PROJECT_ROOT,
        )
        variant_results = tuple(results[variant_id])
        report = build_evaluation_report(variant_results, config)
        reports[variant_id] = report
        write_evaluation_artifacts(
            report,
            variant_results,
            baseline_dir=PROJECT_ROOT / "evals" / "baselines",
            results_dir=PROJECT_ROOT / "evals" / "results",
        )

    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.write_text(
        json.dumps(
            {
                "reranker_model": reranker_provider.model,
                "candidate_pool": args.candidate_pool,
                "cases": traces,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    args.comparison_output.parent.mkdir(parents=True, exist_ok=True)
    args.comparison_output.write_text(
        _comparison_markdown(reports, results, reranker_latencies, args.top_k),
        encoding="utf-8",
    )
    print(f"Comparison: {args.comparison_output}")
    print(f"Trace: {args.trace_output}")
    return 0


def _target_trace(trace: Any, paper_id: str, pages: tuple[int, ...]) -> dict[str, Any]:
    paper_candidates = [item for item in trace.candidates if item.paper_id == paper_id]
    page_candidates = [item for item in paper_candidates if item.page_number in pages]
    return {
        "original_paper_rank": min((item.original_rank for item in paper_candidates), default=None),
        "reranked_paper_rank": min((item.reranked_rank for item in paper_candidates), default=None),
        "original_exact_page_rank": min(
            (item.original_rank for item in page_candidates), default=None
        ),
        "reranked_exact_page_rank": min(
            (item.reranked_rank for item in page_candidates), default=None
        ),
        "best_reranker_score": max(
            (item.reranker_score for item in paper_candidates), default=None
        ),
    }


def _case_result(
    case: RetrievalDiagnosticCase,
    evidence: Sequence[RetrievedChunk],
    queries: Sequence[str],
    latency_ms: float,
) -> RetrievalCaseResult:
    split = "paired_anchor" if "anchor-v1" in case.tags else "challenge"
    return RetrievalCaseResult(
        case_id=case.case_id,
        question=case.question,
        question_type=case.question_type,
        difficulty=case.difficulty,
        evaluation_split=split,
        retrieval_queries=tuple(queries),
        relevant=case.relevant,
        latency_ms=round(latency_ms, 2),
        candidates=tuple(
            RetrievedCandidate(
                rank=rank,
                score=item.score,
                chunk_id=item.chunk.chunk_id,
                paper_id=item.chunk.paper_id,
                page_number=item.chunk.page_number,
                section_title=item.chunk.section_title,
                title=item.chunk.title,
            )
            for rank, item in enumerate(evidence, start=1)
        ),
    )


def _comparison_markdown(
    reports: dict[str, Any],
    results: dict[str, list[RetrievalCaseResult]],
    reranker_latencies: dict[str, list[float]],
    top_k: int,
) -> str:
    order = (
        "reranker_fast_base_v2",
        "reranker_fast_bge_v2",
        "reranker_deep_max_base_v2",
        "reranker_deep_max_bge_v2",
    )
    lines = [
        "# Reranker Ablation v2",
        "",
        "| Strategy | Paper@1 | Paper@10 | Paper MRR | Page@1 | Page@10 | Page MRR | "
        "Paired Complete | Challenge Complete | DS-041 | Retrieval P50/P95 | "
        "Reranker P50/P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for variant_id in order:
        report = reports[variant_id]
        groups = {group.group: group for group in report.by_evaluation_split}
        result_041 = next(item for item in results[variant_id] if item.case_id == "DS-041")
        complete_041 = _is_complete(result_041, top_k)
        rerank_p50 = (
            _percentile(reranker_latencies[variant_id], 0.5)
            if variant_id in reranker_latencies
            else None
        )
        rerank_p95 = (
            _percentile(reranker_latencies[variant_id], 0.95)
            if variant_id in reranker_latencies
            else None
        )
        lines.append(
            f"| {variant_id} | {report.overall.cutoffs[1].paper_recall:.2%} | "
            f"{report.overall.cutoffs[top_k].paper_recall:.2%} | "
            f"{report.overall.paper_mrr:.4f} | "
            f"{report.overall.cutoffs[1].exact_page_recall:.2%} | "
            f"{report.overall.cutoffs[top_k].exact_page_recall:.2%} | "
            f"{report.overall.exact_page_mrr:.4f} | "
            f"{groups['paired_anchor'].cutoffs[top_k].complete_paper_coverage_rate:.2%} | "
            f"{groups['challenge'].cutoffs[top_k].complete_paper_coverage_rate:.2%} | "
            f"{complete_041} | {report.p50_latency_ms:.0f}/{report.p95_latency_ms:.0f} ms | "
            f"{f'{rerank_p50:.0f}/{rerank_p95:.0f} ms' if rerank_p50 else '-'} |"
        )
    return "\n".join(lines) + "\n"


def _is_complete(result: RetrievalCaseResult, top_k: int) -> bool:
    relevant = {item.paper_id for item in result.relevant}
    retrieved = {item.paper_id for item in result.candidates[:top_k] if item.paper_id is not None}
    return relevant <= retrieved


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]


if __name__ == "__main__":
    raise SystemExit(main())
