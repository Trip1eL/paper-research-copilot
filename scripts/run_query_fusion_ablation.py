"""Run query-fusion ablations over one shared set of Dense/BM25 rankings."""

import argparse
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

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
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.retrieval import (
    QUERY_REWRITE_PROMPT_VERSION,
    Bm25Retriever,
    CachedQueryRewriter,
    RetrievalMode,
    find_query_rewrite_alias_leaks,
    fuse_query_rankings_max,
    fuse_rankings,
)


@dataclass(frozen=True)
class FusionVariant:
    variant_id: str
    strategy: str
    fuse: Callable[
        [tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...]],
        tuple[RetrievedChunk, ...],
    ]
    uses_rewrites: bool
    parameters: dict[str, str | int | float | bool]


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
    parser.add_argument("--rewrite-model", default="deepseek-v4-flash")
    parser.add_argument("--rewrite-count", type=int, default=3)
    parser.add_argument("--candidate-pool", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines" / "query_fusion_ablation_v2.md",
    )
    args = parser.parse_args()
    if min(args.candidate_pool, args.rrf_k, args.top_k) < 1:
        raise ValueError("Candidate pool, RRF k, and Top-K must be positive")

    settings = get_settings()
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
    rewriter = CachedQueryRewriter(
        None,
        model=args.rewrite_model,
        cache_path=args.rewrite_cache,
        rewrite_count=args.rewrite_count,
    )
    rewrite_records = [rewriter.record_for(case.question) for case in cases]
    title_leaks = find_query_rewrite_alias_leaks(
        rewrite_records,
        (alias for aliases in paper_aliases.values() for alias in aliases),
    )
    if title_leaks:
        raise ValueError(f"Query rewrites contain forbidden Corpus aliases: {title_leaks}")

    variants = _build_variants(args.top_k, args.rrf_k)
    results_by_variant: dict[str, list[RetrievalCaseResult]] = {
        variant.variant_id: [] for variant in variants
    }
    fusion_latencies: dict[str, list[float]] = {variant.variant_id: [] for variant in variants}

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
            query_rankings: list[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]]] = []
            query_latencies: list[float] = []
            for query in queries:
                started = time.perf_counter()
                query_rankings.append(
                    (
                        dense.retrieve(query, args.candidate_pool),
                        bm25.retrieve(query, args.candidate_pool),
                    )
                )
                query_latencies.append((time.perf_counter() - started) * 1000)
            frozen_rankings = tuple(query_rankings)
            for variant in variants:
                started = time.perf_counter()
                evidence = variant.fuse(frozen_rankings)
                fusion_ms = (time.perf_counter() - started) * 1000
                fusion_latencies[variant.variant_id].append(fusion_ms)
                retrieval_ms = (
                    query_latencies[0] if not variant.uses_rewrites else sum(query_latencies)
                )
                results_by_variant[variant.variant_id].append(
                    _case_result(
                        case,
                        evidence,
                        queries if variant.uses_rewrites else queries[:1],
                        retrieval_ms + fusion_ms,
                    )
                )
            print(f"[{index}/{len(cases)}] {case.case_id}: shared rankings ready")
    finally:
        runtime.close()

    reports = {}
    for variant in variants:
        results = tuple(results_by_variant[variant.variant_id])
        parameters = {
            "candidate_pool_size": args.candidate_pool,
            "rrf_k": args.rrf_k,
            "shared_branch_rankings": True,
            "fusion_mean_ms": round(
                sum(fusion_latencies[variant.variant_id])
                / len(fusion_latencies[variant.variant_id]),
                4,
            ),
            "rewrite_model": args.rewrite_model,
            "rewrite_prompt_version": QUERY_REWRITE_PROMPT_VERSION,
            "rewrite_title_leak_hits": len(title_leaks),
            **variant.parameters,
        }
        config = build_evaluation_config(
            baseline_id=variant.variant_id,
            dataset_path=args.dataset,
            corpus_id=catalog.spec.corpus_id,
            corpus_version=catalog.spec.version,
            collection_name=args.collection,
            embedding_model=settings.siliconflow_embedding_model,
            chunking_version=settings.chunking_version,
            retrieval_strategy=variant.strategy,
            strategy_parameters=parameters,
            top_k=args.top_k,
            cutoffs=(1, 3, 5, args.top_k),
            project_root=PROJECT_ROOT,
        )
        report = build_evaluation_report(results, config)
        reports[variant.variant_id] = report
        write_evaluation_artifacts(
            report,
            results,
            baseline_dir=PROJECT_ROOT / "evals" / "baselines",
            results_dir=PROJECT_ROOT / "evals" / "results",
        )

    args.comparison_output.parent.mkdir(parents=True, exist_ok=True)
    args.comparison_output.write_text(
        _comparison_markdown(variants, reports, results_by_variant, args.top_k),
        encoding="utf-8",
    )
    print(f"Comparison: {args.comparison_output}")
    return 0


def _build_variants(top_k: int, rrf_k: int) -> tuple[FusionVariant, ...]:
    def no_rewrite(
        groups: tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...],
    ) -> tuple[RetrievedChunk, ...]:
        return fuse_rankings(groups[0], top_k=top_k, rrf_k=rrf_k)

    def flat_sum(
        groups: tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...],
    ) -> tuple[RetrievedChunk, ...]:
        return fuse_rankings(
            tuple(ranking for group in groups for ranking in group),
            top_k=top_k,
            rrf_k=rrf_k,
        )

    def weighted(
        original_weight: float,
    ) -> Callable[
        [tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...]],
        tuple[RetrievedChunk, ...],
    ]:
        def apply(
            groups: tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...],
        ) -> tuple[RetrievedChunk, ...]:
            rewrite_weight = (1 - original_weight) / (len(groups) - 1)
            query_weights = (original_weight, *(rewrite_weight for _ in groups[1:]))
            return fuse_rankings(
                tuple(ranking for group in groups for ranking in group),
                top_k=top_k,
                rrf_k=rrf_k,
                ranking_weights=tuple(
                    query_weight for query_weight in query_weights for _ in range(2)
                ),
            )

        return apply

    def max_over_query(
        groups: tuple[tuple[tuple[RetrievedChunk, ...], tuple[RetrievedChunk, ...]], ...],
    ) -> tuple[RetrievedChunk, ...]:
        return fuse_query_rankings_max(groups, top_k=top_k, rrf_k=rrf_k)

    return (
        FusionVariant("query_fusion_no_rewrite_v2", "no_rewrite", no_rewrite, False, {}),
        FusionVariant("query_fusion_flat_sum_v2", "flat_sum_rrf", flat_sum, True, {}),
        FusionVariant(
            "query_fusion_weighted_o040_v2",
            "group_weighted_rrf",
            weighted(0.4),
            True,
            {"original_query_weight": 0.4, "rewrite_group_weight": 0.6},
        ),
        FusionVariant(
            "query_fusion_weighted_o050_v2",
            "group_weighted_rrf",
            weighted(0.5),
            True,
            {"original_query_weight": 0.5, "rewrite_group_weight": 0.5},
        ),
        FusionVariant(
            "query_fusion_weighted_o060_v2",
            "group_weighted_rrf",
            weighted(0.6),
            True,
            {"original_query_weight": 0.6, "rewrite_group_weight": 0.4},
        ),
        FusionVariant(
            "query_fusion_max_over_query_v2",
            "max_over_query_rrf",
            max_over_query,
            True,
            {},
        ),
    )


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
    variants: Sequence[FusionVariant],
    reports: dict[str, object],
    results_by_variant: dict[str, list[RetrievalCaseResult]],
    top_k: int,
) -> str:
    lines = [
        "# Query-aware Fusion Ablation v2",
        "",
        "所有策略复用同一批 Dense/BM25 Top-50，只改变离线融合算法。",
        "",
        "| Strategy | Paper@10 | Exact Page@5 | Exact Page@10 | Page MRR | "
        "Redundancy@10 | Paired Complete | Challenge Complete | Fixed | Kept | Pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for variant in variants:
        report = reports[variant.variant_id]
        overall = report.overall  # type: ignore[attr-defined]
        groups = {group.group: group for group in report.by_evaluation_split}  # type: ignore[attr-defined]
        results = results_by_variant[variant.variant_id]
        fixed = sum(_complete_for_case(results, case_id, top_k) for case_id in _FOCUS_CASES)
        kept = sum(_complete_for_case(results, case_id, top_k) for case_id in _GUARD_CASES)
        accepted = (
            fixed >= 2
            and groups["challenge"].cutoffs[top_k].complete_paper_coverage_rate >= 0.96
            and groups["paired_anchor"].cutoffs[top_k].complete_paper_coverage_rate >= 0.96
            and overall.cutoffs[top_k].exact_page_recall >= 0.9233
            and kept == len(_GUARD_CASES)
        )
        lines.append(
            f"| {variant.strategy} {variant.parameters} | "
            f"{overall.cutoffs[top_k].paper_recall:.2%} | "
            f"{overall.cutoffs[5].exact_page_recall:.2%} | "
            f"{overall.cutoffs[top_k].exact_page_recall:.2%} | "
            f"{overall.exact_page_mrr:.4f} | "
            f"{overall.cutoffs[top_k].same_page_redundancy_rate:.2%} | "
            f"{groups['paired_anchor'].cutoffs[top_k].complete_paper_coverage_rate:.2%} | "
            f"{groups['challenge'].cutoffs[top_k].complete_paper_coverage_rate:.2%} | "
            f"{fixed}/{len(_FOCUS_CASES)} | {kept}/{len(_GUARD_CASES)} | {accepted} |"
        )
    lines.extend(
        [
            "",
            "## 验收条件",
            "",
            "- 修复 `DS-021/025/041` 至少 2 条。",
            "- Challenge Complete Papers@10 不低于 96%。",
            "- Paired Complete Papers@10 不低于 96%。",
            "- Overall Exact Page@10 不低于 92.33%。",
            "- `DS-045/046/049` 必须全部保持完整覆盖。",
            "",
        ]
    )
    return "\n".join(lines)


def _complete_for_case(
    results: Sequence[RetrievalCaseResult],
    case_id: str,
    top_k: int,
) -> bool:
    result = next(item for item in results if item.case_id == case_id)
    relevant = {item.paper_id for item in result.relevant}
    retrieved = {item.paper_id for item in result.candidates[:top_k] if item.paper_id is not None}
    return relevant <= retrieved


_FOCUS_CASES = ("DS-021", "DS-025", "DS-041")
_GUARD_CASES = ("DS-045", "DS-046", "DS-049")


if __name__ == "__main__":
    raise SystemExit(main())
