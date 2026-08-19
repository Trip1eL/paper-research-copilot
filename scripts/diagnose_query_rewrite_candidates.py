"""Diagnose whether Query Rewrite failures are recall or ranking failures."""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import load_retrieval_diagnostics
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.retrieval import (
    QUERY_REWRITE_PROMPT_VERSION,
    Bm25Retriever,
    CachedQueryRewriter,
    RetrievalMode,
    fuse_rankings,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument(
        "--collection",
        default="agent_seed_v2_bge_m3_chunking_v1",
    )
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
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=PROJECT_ROOT / "evals" / "diagnostics" / "query_rewrite_candidates_v2",
    )
    args = parser.parse_args()

    if args.candidate_pool < 1 or args.rrf_k < 1:
        raise ValueError("Candidate pool and RRF k must be positive")
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    page_counts = {asset.spec.paper_id: asset.manifest.page_count for asset in catalog.papers}
    cases = load_retrieval_diagnostics(
        args.dataset,
        allowed_paper_ids=set(page_counts),
        paper_page_counts=page_counts,
    )
    selected_ids = set(args.case_id)
    selected_cases = tuple(
        case for case in cases if not selected_ids or case.case_id in selected_ids
    )
    missing_ids = selected_ids - {case.case_id for case in selected_cases}
    if missing_ids:
        raise ValueError(f"Unknown case IDs: {sorted(missing_ids)}")

    settings = get_settings()
    runtime = build_retrieval_runtime(settings, args.collection)
    try:
        corpus_filter: dict[str, str | int | bool] = {
            "corpus_id": catalog.spec.corpus_id,
            "corpus_version": catalog.spec.version,
            "chunking_version": settings.chunking_version,
        }
        bm25 = Bm25Retriever(runtime.vector_store.list_chunks(corpus_filter))
        dense = runtime.retriever_for(RetrievalMode.EVIDENCE)
        rewriter = CachedQueryRewriter(
            None,
            model=args.rewrite_model,
            cache_path=args.rewrite_cache,
            rewrite_count=args.rewrite_count,
        )
        case_reports: list[dict[str, Any]] = []
        for case in selected_cases:
            queries = (case.question, *rewriter.rewrite(case.question))
            branches: list[dict[str, Any]] = []
            rankings = []
            for query_index, query in enumerate(queries):
                dense_ranking = dense.retrieve(query, args.candidate_pool)
                bm25_ranking = bm25.retrieve(query, args.candidate_pool)
                rankings.extend((dense_ranking, bm25_ranking))
                branches.append(
                    {
                        "query_index": query_index,
                        "query": query,
                        "dense": dense_ranking,
                        "bm25": bm25_ranking,
                    }
                )
            original_fused = fuse_rankings(
                rankings[:2],
                top_k=args.candidate_pool * 2,
                rrf_k=args.rrf_k,
            )
            rewritten_fused = fuse_rankings(
                rankings,
                top_k=args.candidate_pool * len(rankings),
                rrf_k=args.rrf_k,
            )
            targets = [
                _target_diagnostic(
                    relevant.paper_id,
                    relevant.pages,
                    branches,
                    original_fused,
                    rewritten_fused,
                    args.candidate_pool,
                )
                for relevant in case.relevant
            ]
            case_reports.append(
                {
                    "case_id": case.case_id,
                    "question": case.question,
                    "queries": queries,
                    "targets": targets,
                }
            )
            status = ", ".join(
                f"{target['paper_id']}={target['classification']}" for target in targets
            )
            print(f"{case.case_id}: {status}")
    finally:
        runtime.close()

    report = {
        "evaluated_on": date.today().isoformat(),
        "dataset": args.dataset.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "collection": args.collection,
        "embedding_model": settings.siliconflow_embedding_model,
        "rewrite_model": args.rewrite_model,
        "rewrite_prompt_version": QUERY_REWRITE_PROMPT_VERSION,
        "rewrite_cache": args.rewrite_cache.resolve()
        .relative_to(PROJECT_ROOT.resolve())
        .as_posix(),
        "candidate_pool": args.candidate_pool,
        "rrf_k": args.rrf_k,
        "cases": case_reports,
    }
    json_path = args.output_prefix.with_suffix(".json")
    markdown_path = args.output_prefix.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


def _target_diagnostic(
    paper_id: str,
    pages: tuple[int, ...],
    branches: list[dict[str, Any]],
    original_fused: tuple[Any, ...],
    rewritten_fused: tuple[Any, ...],
    candidate_pool: int,
) -> dict[str, Any]:
    branch_ranks = [
        {
            "query_index": branch["query_index"],
            "dense_paper_rank": _rank(branch["dense"], paper_id),
            "dense_exact_page_rank": _rank(branch["dense"], paper_id, pages),
            "bm25_paper_rank": _rank(branch["bm25"], paper_id),
            "bm25_exact_page_rank": _rank(branch["bm25"], paper_id, pages),
        }
        for branch in branches
    ]
    original_rank = _rank(original_fused, paper_id)
    rewritten_rank = _rank(rewritten_fused, paper_id)
    if rewritten_rank is None:
        classification = "not_recalled_in_branches"
    elif rewritten_rank <= 10:
        classification = "top_10"
    elif rewritten_rank <= candidate_pool:
        classification = "rerankable_11_50"
    else:
        classification = "outside_fused_top_50"
    return {
        "paper_id": paper_id,
        "relevant_pages": pages,
        "original_fused_paper_rank": original_rank,
        "original_fused_exact_page_rank": _rank(original_fused, paper_id, pages),
        "rewritten_fused_paper_rank": rewritten_rank,
        "rewritten_fused_exact_page_rank": _rank(rewritten_fused, paper_id, pages),
        "classification": classification,
        "branch_ranks": branch_ranks,
    }


def _rank(
    ranking: tuple[Any, ...],
    paper_id: str,
    pages: tuple[int, ...] | None = None,
) -> int | None:
    return next(
        (
            rank
            for rank, item in enumerate(ranking, start=1)
            if item.chunk.paper_id == paper_id
            and (pages is None or item.chunk.page_number in pages)
        ),
        None,
    )


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Query Rewrite Candidate Pool 诊断",
        "",
        f"- Collection：`{report['collection']}`",
        f"- Candidate Pool：`{report['candidate_pool']}`",
        f"- RRF k：`{report['rrf_k']}`",
        f"- Rewrite：`{report['rewrite_model']}` / `{report['rewrite_prompt_version']}`",
        "",
        "| Case | Target Paper | Original RRF Rank | Rewrite RRF Rank | "
        "Exact Page Rank | Classification |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for case in report["cases"]:
        for target in case["targets"]:
            lines.append(
                f"| {case['case_id']} | {target['paper_id']} | "
                f"{target['original_fused_paper_rank'] or '-'} | "
                f"{target['rewritten_fused_paper_rank'] or '-'} | "
                f"{target['rewritten_fused_exact_page_rank'] or '-'} | "
                f"{target['classification']} |"
            )
    lines.extend(
        [
            "",
            "## 口径",
            "",
            "- `rerankable_11_50` 表示目标已进入融合 Top-50，Reranker 有机会提升到 Top-10。",
            "- `outside_fused_top_50` 表示分支召回了目标，但当前 Top-50 Reranker 看不到它。",
            "- `not_recalled_in_branches` 表示 8 路 Dense/BM25 Top-50 都没有目标论文。",
            "- JSON 文件保留每条 Query 的 Dense/BM25 Paper Rank 与 Exact Page Rank。",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
