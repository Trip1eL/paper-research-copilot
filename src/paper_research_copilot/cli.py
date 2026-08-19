"""Command-line interface for the base PDF RAG pipeline."""

import argparse
import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

from paper_research_copilot.agent import (
    AgentResult,
    AgentRuntimeConfig,
    build_agent_runtime,
)
from paper_research_copilot.config import PROJECT_ROOT, Settings, get_settings
from paper_research_copilot.domain import Answer, PaperChunk, ParsedDocument, RetrievedChunk
from paper_research_copilot.evaluation import (
    AnswerCaseResult,
    AnswerEvaluationCase,
    AnswerEvaluationReport,
    CachedAnswerJudge,
    JudgeCaseResult,
    JudgeEvaluationReport,
    RetrievalCaseResult,
    RetrievalEvaluationReport,
    build_answer_evaluation_config,
    build_answer_evaluation_report,
    build_evaluation_config,
    build_evaluation_report,
    build_judge_evaluation_config,
    build_judge_evaluation_report,
    load_answer_evaluation_cases,
    load_retrieval_diagnostics,
    run_answer_evaluation,
    run_judge_evaluation,
    run_retrieval_evaluation,
    write_answer_evaluation_artifacts,
    write_evaluation_artifacts,
    write_judge_evaluation_artifacts,
)
from paper_research_copilot.ingestion import (
    CorpusCatalogLoader,
    CorpusPreparer,
    PageAwareChunker,
    PdfParser,
    PreparedCorpus,
    PreparedPaper,
    calculate_chunk_statistics,
    write_chunk_statistics,
)
from paper_research_copilot.integrations import (
    OpenAICompatibleChatProvider,
    SiliconFlowRerankerProvider,
)
from paper_research_copilot.pipeline import (
    build_corpus_ingestion_pipeline,
    build_pipeline,
    build_retrieval_runtime,
)
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.reporting.prompts import (
    ANSWER_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from paper_research_copilot.retrieval import (
    QUERY_REWRITE_PROMPT_VERSION,
    Bm25Retriever,
    CachedQueryRewriter,
    CandidateRetriever,
    DiversifiedDenseRetriever,
    HybridMmrRetriever,
    MmrDenseRetriever,
    MultiQueryRrfRetriever,
    QdrantVectorStore,
    RerankingRetriever,
    RetrievalMode,
    RrfFusionRetriever,
    find_query_rewrite_alias_leaks,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Parse and index PDF files")
    ingest_parser.add_argument("pdfs", nargs="+", type=Path)

    ingest_corpus_parser = subparsers.add_parser(
        "ingest-corpus", help="Validate and idempotently index a versioned corpus"
    )
    ingest_corpus_parser.add_argument("--version", type=_positive_int, default=1)
    ingest_corpus_parser.add_argument(
        "--collection",
        help="Override Qdrant collection without changing .env",
    )

    corpus_stats_parser = subparsers.add_parser(
        "corpus-stats", help="Generate offline Chunk statistics for a versioned corpus"
    )
    corpus_stats_parser.add_argument("--version", type=_positive_int, default=1)

    evaluate_parser = subparsers.add_parser(
        "evaluate-retriever", help="Evaluate retrieval strategies without calling an LLM"
    )
    evaluate_parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "retrieval_diagnostic_v1.jsonl",
    )
    evaluate_parser.add_argument("--version", type=_positive_int, default=1)
    evaluate_parser.add_argument(
        "--collection",
        help="Override Qdrant collection without changing .env",
    )
    evaluate_parser.add_argument("--top-k", type=_positive_int, default=10)
    evaluate_parser.add_argument("--baseline-id", default="dense_v1")
    evaluate_parser.add_argument(
        "--strategy",
        choices=(
            "dense",
            "diversified_dense",
            "mmr_dense",
            "bm25",
            "hybrid_rrf",
            "hybrid_rrf_mmr",
            "hybrid_rrf_query_rewrite",
        ),
        default="dense",
    )
    evaluate_parser.add_argument("--candidate-pool", type=_positive_int, default=50)
    evaluate_parser.add_argument("--max-per-paper", type=_positive_int, default=3)
    evaluate_parser.add_argument("--max-per-page", type=_positive_int, default=1)
    evaluate_parser.add_argument("--mmr-lambda", type=_unit_float, default=0.85)
    evaluate_parser.add_argument("--bm25-k1", type=_positive_float, default=1.5)
    evaluate_parser.add_argument("--bm25-b", type=_unit_float, default=0.75)
    evaluate_parser.add_argument("--rrf-k", type=_positive_int, default=60)
    evaluate_parser.add_argument("--rewrite-count", type=_positive_int, default=3)
    evaluate_parser.add_argument("--rewrite-model", default=None)
    evaluate_parser.add_argument("--rewrite-cache", type=Path, default=None)

    answer_evaluate_parser = subparsers.add_parser(
        "evaluate-answer",
        help="Evaluate grounded answers and citations with deterministic metrics",
    )
    answer_evaluate_parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    answer_evaluate_parser.add_argument("--version", type=_positive_int, default=2)
    answer_evaluate_parser.add_argument(
        "--collection",
        default="agent_seed_v2_bge_m3_chunking_v1",
    )
    answer_evaluate_parser.add_argument("--top-k", type=_positive_int, default=10)
    answer_evaluate_parser.add_argument("--candidate-pool", type=_positive_int, default=50)
    answer_evaluate_parser.add_argument("--baseline-id", default="answer_hybrid_rrf_v1")
    answer_evaluate_parser.add_argument(
        "--strategy",
        choices=("hybrid_rrf", "hybrid_rrf_rerank"),
        default="hybrid_rrf",
    )

    judge_parser = subparsers.add_parser(
        "evaluate-judge",
        help="Evaluate saved answers with the cached gpt-5.5 LLM Judge",
    )
    judge_parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    judge_parser.add_argument(
        "--answer-baseline",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines" / "answer_hybrid_rrf_v1.json",
    )
    judge_parser.add_argument(
        "--answer-results",
        type=Path,
        default=PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_v1.jsonl",
    )
    judge_parser.add_argument(
        "--baseline-id",
        default="answer_hybrid_rrf_gpt55_judge_v1",
    )
    judge_parser.add_argument("--cache", type=Path, default=None)
    judge_parser.add_argument("--case-id", action="append", default=[])
    judge_parser.add_argument("--retry-attempts", type=_positive_int, default=3)

    agent_parser = subparsers.add_parser(
        "agent",
        help="Run the bounded LangGraph research workflow",
    )
    agent_parser.add_argument("question")
    agent_parser.add_argument("--version", type=_positive_int, default=3)
    agent_parser.add_argument(
        "--collection",
        default="agent_seed_v3_bge_m3_chunking_v1",
    )
    agent_parser.add_argument("--top-k", type=_positive_int, default=None)
    agent_parser.add_argument("--candidate-pool", type=_positive_int, default=None)
    agent_parser.add_argument("--max-retries", type=int, choices=(0, 1), default=None)
    agent_parser.add_argument("--min-chunks-per-task", type=_positive_int, default=None)
    agent_parser.add_argument("--planner-cache", type=Path, default=None)
    agent_parser.add_argument("--show-trace", action="store_true")

    ask_parser = subparsers.add_parser("ask", help="Answer from indexed evidence")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", type=_positive_int, default=None)
    _add_retrieval_mode_argument(ask_parser)

    run_parser = subparsers.add_parser("run", help="Index PDFs and answer one question")
    run_parser.add_argument("question")
    run_parser.add_argument("pdfs", nargs="+", type=Path)
    run_parser.add_argument("--top-k", type=_positive_int, default=None)

    inspect_pdf_parser = subparsers.add_parser(
        "inspect-pdf", help="Show parsed PDF metadata and page statistics"
    )
    inspect_pdf_parser.add_argument("pdf", type=Path)
    inspect_pdf_parser.add_argument("--preview-chars", type=_positive_int, default=160)

    inspect_chunks_parser = subparsers.add_parser(
        "inspect-chunks", help="Show page-aware chunks before embedding"
    )
    inspect_chunks_parser.add_argument("pdf", type=Path)
    inspect_chunks_parser.add_argument("--limit", type=_positive_int, default=10)
    inspect_chunks_parser.add_argument("--page", type=_positive_int, default=None)
    inspect_chunks_parser.add_argument("--full-text", action="store_true")

    search_parser = subparsers.add_parser(
        "search", help="Show retrieval results without calling the LLM"
    )
    search_parser.add_argument("question")
    search_parser.add_argument("--top-k", type=_positive_int, default=None)
    _add_retrieval_mode_argument(search_parser)

    prompt_parser = subparsers.add_parser(
        "show-prompt", help="Show the exact prompts without calling the LLM"
    )
    prompt_parser.add_argument("question")
    prompt_parser.add_argument("--top-k", type=_positive_int, default=None)
    _add_retrieval_mode_argument(prompt_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    if args.command in {"inspect-pdf", "inspect-chunks"}:
        document = PdfParser().parse(_resolve_pdf_paths((args.pdf,))[0])
        if args.command == "inspect-pdf":
            _print_document(document, preview_chars=args.preview_chars)
        else:
            _print_chunks(
                _build_chunker(settings).split(document),
                limit=args.limit,
                page=args.page,
                full_text=args.full_text,
            )
        return 0

    if args.command == "corpus-stats":
        catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
        prepared = CorpusPreparer(PdfParser(), _build_chunker(settings)).prepare(catalog)
        stats_path = _write_corpus_statistics(prepared, settings)
        print(f"Prepared {len(prepared.papers)} paper(s), {len(prepared.chunks)} chunk(s).")
        print(f"Chunk report: {stats_path}")
        return 0

    if args.command == "ingest-corpus":
        catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
        corpus_pipeline = build_corpus_ingestion_pipeline(settings, args.collection)
        try:
            prepared = corpus_pipeline.prepare(catalog)
            stats_path = _write_corpus_statistics(prepared, settings)
            print(f"Prepared {len(prepared.papers)} paper(s), {len(prepared.chunks)} chunk(s).")
            print(f"Chunk report: {stats_path}")
            summary = corpus_pipeline.ingest(prepared, progress=_print_corpus_progress)
            indexed_count = corpus_pipeline.count(prepared)
            print(
                f"Indexed {summary.document_count} document(s), "
                f"{summary.page_count} page(s), {summary.chunk_count} chunk(s)."
            )
            print(f"Collection: {summary.collection_name} (points={indexed_count})")
            return 0
        finally:
            corpus_pipeline.close()

    if args.command == "evaluate-retriever":
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
        runtime = build_retrieval_runtime(settings, args.collection)
        try:
            if runtime.vector_store.count() == 0:
                raise LookupError("Qdrant collection is empty; run ingest-corpus first.")
            strategy_parameters: dict[str, str | int | float | bool] = {}
            dense_retriever = runtime.retriever_for(RetrievalMode.EVIDENCE)
            retriever: CandidateRetriever = dense_retriever
            if args.strategy == "diversified_dense":
                strategy_parameters = {
                    "candidate_pool_size": args.candidate_pool,
                    "max_chunks_per_paper": args.max_per_paper,
                    "max_chunks_per_page": args.max_per_page,
                }
                retriever = DiversifiedDenseRetriever(
                    dense_retriever,
                    candidate_pool_size=args.candidate_pool,
                    max_chunks_per_paper=args.max_per_paper,
                    max_chunks_per_page=args.max_per_page,
                )
            elif args.strategy == "mmr_dense":
                strategy_parameters = {
                    "candidate_pool_size": args.candidate_pool,
                    "lambda_mult": args.mmr_lambda,
                }
                retriever = MmrDenseRetriever(
                    runtime.embeddings,
                    runtime.vector_store,
                    candidate_pool_size=args.candidate_pool,
                    lambda_mult=args.mmr_lambda,
                )
            elif args.strategy in {
                "bm25",
                "hybrid_rrf",
                "hybrid_rrf_mmr",
                "hybrid_rrf_query_rewrite",
            }:
                corpus_filter: dict[str, str | int | bool] = {
                    "corpus_id": catalog.spec.corpus_id,
                    "corpus_version": catalog.spec.version,
                    "chunking_version": settings.chunking_version,
                }
                chunks = runtime.vector_store.list_chunks(corpus_filter)
                bm25_retriever = Bm25Retriever(
                    chunks,
                    k1=args.bm25_k1,
                    b=args.bm25_b,
                )
                print(f"BM25 index: {bm25_retriever.chunk_count} chunk(s)")
                strategy_parameters = {
                    "bm25_k1": args.bm25_k1,
                    "bm25_b": args.bm25_b,
                    "tokenizer": "english_stopwords_porter_stemmer",
                }
                if args.strategy == "bm25":
                    retriever = bm25_retriever
                else:
                    strategy_parameters.update(
                        {
                            "candidate_pool_size": args.candidate_pool,
                            "rrf_k": args.rrf_k,
                        }
                    )
                    fusion_retriever = RrfFusionRetriever(
                        dense_retriever,
                        bm25_retriever,
                        candidate_pool_size=args.candidate_pool,
                        rrf_k=args.rrf_k,
                    )
                    retriever = fusion_retriever
                    if args.strategy == "hybrid_rrf_mmr":
                        strategy_parameters["lambda_mult"] = args.mmr_lambda
                        strategy_parameters["rrf_score_normalization"] = "min_max"
                        retriever = HybridMmrRetriever(
                            fusion_retriever,
                            runtime.vector_store,
                            candidate_pool_size=args.candidate_pool,
                            lambda_mult=args.mmr_lambda,
                        )
                    elif args.strategy == "hybrid_rrf_query_rewrite":
                        llm_url, llm_key = settings.require_llm_credentials()
                        rewrite_model = args.rewrite_model or settings.deepseek_model
                        cache_path = args.rewrite_cache or (
                            PROJECT_ROOT
                            / "evals"
                            / "query_rewrites"
                            / (
                                f"{args.dataset.stem}_{rewrite_model}_"
                                f"{QUERY_REWRITE_PROMPT_VERSION}.jsonl"
                            )
                        )
                        query_rewriter = CachedQueryRewriter(
                            OpenAICompatibleChatProvider(
                                base_url=llm_url,
                                api_key=llm_key,
                                model=rewrite_model,
                                max_tokens=2000,
                            ),
                            model=rewrite_model,
                            cache_path=cache_path,
                            rewrite_count=args.rewrite_count,
                        )
                        for case in cases:
                            query_rewriter.rewrite(case.question)
                        rewrite_records = [
                            query_rewriter.record_for(case.question) for case in cases
                        ]
                        title_leaks = find_query_rewrite_alias_leaks(
                            rewrite_records,
                            (alias for aliases in paper_aliases.values() for alias in aliases),
                        )
                        if title_leaks:
                            raise ValueError(
                                f"Query rewrites contain forbidden Corpus aliases: {title_leaks}"
                            )
                        rewrite_latencies = [
                            record.generation_latency_ms for record in rewrite_records
                        ]
                        strategy_parameters.update(
                            {
                                "rewrite_model": rewrite_model,
                                "rewrite_count": args.rewrite_count,
                                "rewrite_retry_attempts": query_rewriter.retry_attempts,
                                "rewrite_prompt_version": QUERY_REWRITE_PROMPT_VERSION,
                                "rewrite_cache": cache_path.resolve()
                                .relative_to(PROJECT_ROOT.resolve())
                                .as_posix(),
                                "rewrite_generation_mean_ms": round(
                                    sum(rewrite_latencies) / len(rewrite_latencies), 2
                                ),
                                "rewrite_title_leak_hits": len(title_leaks),
                            }
                        )
                        print(
                            f"Query rewrites: {len(cases)} case(s), "
                            "mean_generation="
                            f"{strategy_parameters['rewrite_generation_mean_ms']} ms"
                        )
                        print(f"Query rewrite cache: {cache_path}")
                        retriever = MultiQueryRrfRetriever(
                            dense_retriever,
                            bm25_retriever,
                            query_rewriter,
                            candidate_pool_size=args.candidate_pool,
                            rrf_k=args.rrf_k,
                        )
            results = run_retrieval_evaluation(
                retriever,
                cases,
                top_k=args.top_k,
                progress=_print_evaluation_progress,
            )
            cutoffs = tuple(
                sorted({cutoff for cutoff in (1, 3, 5, 10, args.top_k) if cutoff <= args.top_k})
            )
            config = build_evaluation_config(
                baseline_id=args.baseline_id,
                dataset_path=args.dataset,
                corpus_id=catalog.spec.corpus_id,
                corpus_version=catalog.spec.version,
                collection_name=runtime.vector_store.collection_name,
                embedding_model=settings.siliconflow_embedding_model,
                chunking_version=settings.chunking_version,
                retrieval_strategy=args.strategy,
                strategy_parameters=strategy_parameters,
                top_k=args.top_k,
                cutoffs=cutoffs,
                project_root=PROJECT_ROOT,
            )
            report = build_evaluation_report(results, config)
            json_path, markdown_path, raw_path = write_evaluation_artifacts(
                report,
                results,
                baseline_dir=PROJECT_ROOT / "evals" / "baselines",
                results_dir=PROJECT_ROOT / "evals" / "results",
            )
            _print_evaluation_summary(report)
            print(f"Baseline JSON: {json_path}")
            print(f"Baseline report: {markdown_path}")
            print(f"Raw results: {raw_path}")
            return 0
        finally:
            runtime.close()

    if args.command == "evaluate-answer":
        catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
        page_counts = {asset.spec.paper_id: asset.manifest.page_count for asset in catalog.papers}
        answer_cases = load_answer_evaluation_cases(
            args.dataset,
            allowed_paper_ids=set(page_counts),
            paper_page_counts=page_counts,
        )
        llm_url, llm_key = settings.require_llm_credentials()
        runtime = build_retrieval_runtime(settings, args.collection)
        try:
            if runtime.vector_store.count() == 0:
                raise LookupError("Qdrant collection is empty; run ingest-corpus first.")
            retriever = runtime.retriever_for(RetrievalMode.DISCOVERY)
            answer_strategy_parameters: dict[str, str | int | float | bool] = {
                "candidate_pool_size": args.candidate_pool,
                "rrf_k": 60,
            }
            if args.strategy == "hybrid_rrf_rerank":
                siliconflow_url, siliconflow_key = settings.require_siliconflow_credentials()
                retriever = RerankingRetriever(
                    retriever,
                    SiliconFlowRerankerProvider(
                        siliconflow_url,
                        siliconflow_key,
                        settings.siliconflow_reranker_model,
                    ),
                    candidate_pool_size=args.candidate_pool,
                )
                answer_strategy_parameters["reranker_model"] = settings.siliconflow_reranker_model
            answer_generator = AnswerGenerator(
                OpenAICompatibleChatProvider(
                    base_url=llm_url,
                    api_key=llm_key,
                    model=settings.deepseek_model,
                    max_tokens=settings.answer_max_tokens,
                )
            )
            answer_results = run_answer_evaluation(
                retriever,
                answer_generator,
                answer_cases,
                top_k=args.top_k,
                progress=_print_answer_evaluation_progress,
            )
            answer_config = build_answer_evaluation_config(
                baseline_id=args.baseline_id,
                dataset_path=args.dataset,
                corpus_id=catalog.spec.corpus_id,
                corpus_version=catalog.spec.version,
                collection_name=runtime.vector_store.collection_name,
                retrieval_strategy=args.strategy,
                retrieval_parameters=answer_strategy_parameters,
                answer_model=settings.deepseek_model,
                answer_prompt_version=ANSWER_PROMPT_VERSION,
                answer_retry_attempts=answer_generator.retry_attempts,
                top_k=args.top_k,
                project_root=PROJECT_ROOT,
            )
            answer_report = build_answer_evaluation_report(answer_results, answer_config)
            json_path, markdown_path, raw_path = write_answer_evaluation_artifacts(
                answer_report,
                answer_results,
                baseline_dir=PROJECT_ROOT / "evals" / "baselines",
                results_dir=PROJECT_ROOT / "evals" / "results",
            )
            _print_answer_evaluation_summary(answer_report)
            print(f"Baseline JSON: {json_path}")
            print(f"Baseline report: {markdown_path}")
            print(f"Raw results: {raw_path}")
            return 0
        finally:
            runtime.close()

    if args.command == "evaluate-judge":
        answer_report = AnswerEvaluationReport.model_validate_json(
            args.answer_baseline.read_text(encoding="utf-8")
        )
        dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
        if answer_report.config.dataset_sha256 != dataset_sha256:
            raise ValueError(
                "Answer Baseline and Judge dataset SHA-256 differ; refusing an invalid comparison"
            )
        answer_results = _load_answer_results(args.answer_results)
        answer_cases = load_answer_evaluation_cases(args.dataset)
        _validate_judge_inputs(
            answer_cases,
            answer_results,
            expected_count=answer_report.case_count,
        )

        selected_case_ids = set(args.case_id)
        if selected_case_ids:
            known_case_ids = {case.case_id for case in answer_cases}
            unknown_case_ids = selected_case_ids - known_case_ids
            if unknown_case_ids:
                raise ValueError(f"Unknown Judge Case IDs: {sorted(unknown_case_ids)}")
            answer_cases = tuple(case for case in answer_cases if case.case_id in selected_case_ids)
            answer_results = tuple(
                result for result in answer_results if result.case_id in selected_case_ids
            )

        relay_url, relay_key = settings.require_relay_credentials()
        cache_path = args.cache or (
            PROJECT_ROOT
            / "evals"
            / "judges"
            / (
                f"{answer_report.config.baseline_id}_{settings.gpt_model_name}_"
                "answer_judge_v1.jsonl"
            )
        )
        runtime = build_retrieval_runtime(
            settings,
            answer_report.config.collection_name,
        )
        try:
            evidence_text = _load_judge_evidence_text(answer_results, runtime.vector_store)
            judge = CachedAnswerJudge(
                OpenAICompatibleChatProvider(
                    base_url=relay_url,
                    api_key=relay_key,
                    model=settings.gpt_model_name,
                    max_tokens=4000,
                ),
                model=settings.gpt_model_name,
                cache_path=cache_path,
                retry_attempts=args.retry_attempts,
            )
            judge_results = run_judge_evaluation(
                judge,
                answer_cases,
                answer_results,
                evidence_text_by_chunk_id=evidence_text,
                progress=_print_judge_progress,
            )
            judge_config = build_judge_evaluation_config(
                baseline_id=args.baseline_id,
                dataset_path=args.dataset,
                answer_baseline_id=answer_report.config.baseline_id,
                answer_results_path=args.answer_results,
                judge_model=settings.gpt_model_name,
                retry_attempts=args.retry_attempts,
                project_root=PROJECT_ROOT,
            )
            judge_report = build_judge_evaluation_report(judge_results, judge_config)
            json_path, markdown_path, raw_path = write_judge_evaluation_artifacts(
                judge_report,
                judge_results,
                baseline_dir=PROJECT_ROOT / "evals" / "baselines",
                results_dir=PROJECT_ROOT / "evals" / "results",
            )
            _print_judge_summary(judge_report)
            print(f"Judge cache: {cache_path}")
            print(f"Baseline JSON: {json_path}")
            print(f"Baseline report: {markdown_path}")
            print(f"Raw results: {raw_path}")
            return 0
        finally:
            runtime.close()

    if args.command in {"search", "show-prompt"}:
        runtime = build_retrieval_runtime(settings)
        try:
            evidence = runtime.retrieve(
                args.question,
                args.top_k or settings.retrieval_top_k,
                args.retrieval_mode,
            )
            if not evidence:
                raise LookupError("No evidence found. Ingest at least one PDF first.")
            if args.command == "search":
                _print_search_results(args.question, evidence, args.retrieval_mode)
            else:
                _print_prompt(args.question, evidence)
            return 0
        finally:
            runtime.close()

    if args.command == "agent":
        agent_config = AgentRuntimeConfig(
            top_k=args.top_k or settings.agent_top_k,
            candidate_pool_per_task=(args.candidate_pool or settings.agent_candidate_pool_per_task),
            max_retries=(
                args.max_retries if args.max_retries is not None else settings.agent_max_retries
            ),
            min_chunks_per_task=(args.min_chunks_per_task or settings.agent_min_chunks_per_task),
        )
        agent_runtime = build_agent_runtime(
            settings,
            version=args.version,
            collection_name=args.collection,
            planner_cache_path=args.planner_cache,
            config=agent_config,
        )
        try:
            result = agent_runtime.run(args.question)
            _print_answer(result.answer)
            if args.show_trace:
                _print_agent_trace(result)
            return 0
        finally:
            agent_runtime.close()

    pipeline = build_pipeline(settings)
    try:
        if args.command == "ingest":
            summary = pipeline.ingest(_resolve_pdf_paths(args.pdfs))
            print(
                f"Indexed {summary.document_count} document(s), "
                f"{summary.page_count} page(s), {summary.chunk_count} chunk(s)."
            )
            return 0
        if args.command == "run":
            pipeline.ingest(_resolve_pdf_paths(args.pdfs))
        retrieval_mode = getattr(args, "retrieval_mode", RetrievalMode.EVIDENCE)
        answer = pipeline.ask(args.question, args.top_k, retrieval_mode)
        _print_answer(answer)
        return 0
    finally:
        pipeline.close()


def _build_chunker(settings: Settings) -> PageAwareChunker:
    return PageAwareChunker(
        chunk_size=settings.chunk_size_chars,
        overlap=settings.chunk_overlap_chars,
        chunking_version=settings.chunking_version,
    )


def _write_corpus_statistics(prepared: PreparedCorpus, settings: Settings) -> Path:
    stats = calculate_chunk_statistics(
        prepared,
        chunking_version=settings.chunking_version,
        chunk_size_chars=settings.chunk_size_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    output_dir = (
        PROJECT_ROOT / "corpus" / f"v{prepared.catalog.spec.version}" / settings.chunking_version
    )
    write_chunk_statistics(stats, output_dir)
    return output_dir / "chunk_report.md"


def _print_corpus_progress(paper: PreparedPaper, index: int, total: int) -> None:
    print(f"[{index}/{total}] {paper.asset.spec.slug}: indexed {len(paper.chunks)} chunk(s)")


def _resolve_pdf_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for path in paths:
        expanded = path.expanduser()
        if expanded.is_absolute() or expanded.exists():
            resolved.append(expanded.resolve())
            continue
        project_candidate = PROJECT_ROOT / expanded
        resolved.append(project_candidate.resolve() if project_candidate.exists() else expanded)
    return tuple(resolved)


def _print_document(document: ParsedDocument, preview_chars: int) -> None:
    metadata = document.metadata
    print("PDF")
    print(f"  Title: {metadata.title}")
    print(f"  Authors: {', '.join(metadata.authors) if metadata.authors else '(missing)'}")
    print(f"  Pages: {metadata.page_count}")
    print(f"  Document SHA-256: {metadata.document_sha256}")
    print(f"  Source: {metadata.source_path}")
    print("\nParsed pages:")
    for page in document.pages:
        preview = _preview(page.text, preview_chars) if page.text else "(no extractable text)"
        print(f"  Page {page.page_number}: chars={len(page.text)}")
        print(f"    {preview}")


def _print_chunks(
    chunks: Sequence[PaperChunk],
    *,
    limit: int,
    page: int | None,
    full_text: bool,
) -> None:
    filtered = [chunk for chunk in chunks if page is None or chunk.page_number == page]
    visible = filtered[:limit]
    page_label = f" on page {page}" if page is not None else ""
    print(f"Chunks: showing {len(visible)} of {len(filtered)}{page_label} (total={len(chunks)})")
    for chunk in visible:
        text = chunk.text if full_text else _preview(chunk.text, 300)
        print(
            f"\nChunk {chunk.chunk_index} | page={chunk.page_number} "
            f"chars={chunk.char_start}:{chunk.char_end} | id={chunk.chunk_id}"
        )
        print(
            f"Strategy: {chunk.chunking_version} | Section: {chunk.section_title or '(unresolved)'}"
        )
        print(text)


def _print_evaluation_progress(
    result: RetrievalCaseResult,
    index: int,
    total: int,
) -> None:
    top = result.candidates[0] if result.candidates else None
    top_label = f"{top.paper_id}/p{top.page_number}" if top else "no-result"
    print(
        f"[{index}/{total}] {result.case_id}: top1={top_label}, latency={result.latency_ms:.0f}ms"
    )


def _print_evaluation_summary(report: RetrievalEvaluationReport) -> None:
    print(f"Evaluated {report.case_count} case(s).")
    for cutoff, metrics in sorted(report.overall.cutoffs.items()):
        print(
            f"K={cutoff}: paper_recall={metrics.paper_recall:.4f}, "
            f"exact_page_recall={metrics.exact_page_recall:.4f}, "
            f"same_page_redundancy={metrics.same_page_redundancy_rate:.4f}"
        )
    print(
        f"MRR: paper={report.overall.paper_mrr:.4f}, exact_page={report.overall.exact_page_mrr:.4f}"
    )


def _print_answer_evaluation_progress(
    result: AnswerCaseResult,
    index: int,
    total: int,
) -> None:
    key_point_recall = result.metrics.key_point_recall
    key_point_label = "-" if key_point_recall is None else f"{key_point_recall:.0%}"
    print(
        f"[{index}/{total}] {result.case_id}: status={result.answer_status}, "
        f"key_points={key_point_label}, latency={result.total_latency_ms:.0f}ms"
    )


def _print_answer_evaluation_summary(report: AnswerEvaluationReport) -> None:
    print(
        f"Evaluated {report.case_count} case(s): answerable={report.answerable_count}, "
        f"unanswerable={report.unanswerable_count}."
    )
    print(
        f"Answerability={report.answerability_accuracy:.4f}, "
        f"key_point_recall={report.key_point_recall:.4f}, "
        f"citation_paper_recall={report.citation_paper_recall:.4f}, "
        f"strict_page_recall={report.strict_page_recall:.4f}"
    )
    print(
        f"Sentence citation coverage={report.sentence_citation_coverage:.4f}, "
        f"P50/P95={report.p50_total_latency_ms:.0f}/{report.p95_total_latency_ms:.0f}ms"
    )


def _load_answer_results(path: Path) -> tuple[AnswerCaseResult, ...]:
    return tuple(
        AnswerCaseResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _validate_judge_inputs(
    cases: Sequence[AnswerEvaluationCase],
    results: Sequence[AnswerCaseResult],
    *,
    expected_count: int,
) -> None:
    case_ids = [case.case_id for case in cases]
    result_ids = [result.case_id for result in results]
    if len(case_ids) != len(set(case_ids)) or len(result_ids) != len(set(result_ids)):
        raise ValueError("Judge inputs contain duplicate Case IDs")
    if set(case_ids) != set(result_ids):
        raise ValueError("Answer Results and Judge dataset must contain identical Case IDs")
    if len(results) != expected_count:
        raise ValueError("Answer Results count does not match the Answer Baseline dataset")


def _load_judge_evidence_text(
    results: Sequence[AnswerCaseResult],
    vector_store: QdrantVectorStore,
) -> dict[str, str]:
    inline_text = {
        evidence.chunk_id: evidence.text
        for result in results
        for evidence in result.evidence
        if evidence.text
    }
    required_chunk_ids = {citation.chunk_id for result in results for citation in result.citations}
    missing_chunk_ids = required_chunk_ids - inline_text.keys()
    if missing_chunk_ids:
        chunks = vector_store.list_chunks()
        inline_text.update(
            {chunk.chunk_id: chunk.text for chunk in chunks if chunk.chunk_id in missing_chunk_ids}
        )
    unresolved = required_chunk_ids - inline_text.keys()
    if unresolved:
        raise LookupError(f"Missing cited Evidence chunks in Qdrant: {sorted(unresolved)}")
    return inline_text


def _print_judge_progress(result: JudgeCaseResult, index: int, total: int) -> None:
    decision = result.decision
    print(
        f"[{index}/{total}] {result.case_id}: source={result.source}, "
        f"scores={decision.correctness.score}/{decision.faithfulness.score}/"
        f"{decision.citation_completeness.score}, latency={result.model_latency_ms:.0f}ms"
    )


def _print_judge_summary(report: JudgeEvaluationReport) -> None:
    print(
        f"Judged {report.case_count} case(s): LLM={report.llm_judged_count}, "
        f"deterministic={report.deterministic_count}, failures={report.judge_failure_count}."
    )
    print(
        f"Correctness={report.correctness:.4f}, Faithfulness={report.faithfulness:.4f}, "
        f"Citation Completeness={report.citation_completeness:.4f}, "
        f"Overall={report.overall_score:.4f}"
    )
    print(
        f"Judge P50/P95={report.p50_model_latency_ms:.0f}/"
        f"{report.p95_model_latency_ms:.0f}ms, Tokens="
        f"{report.total_input_tokens}/{report.total_output_tokens}"
    )


def _print_search_results(
    question: str,
    evidence: Sequence[RetrievedChunk],
    retrieval_mode: RetrievalMode,
) -> None:
    print(f"Question: {question}")
    print(f"Retrieval mode: {retrieval_mode.value}")
    print(f"Retrieval results: {len(evidence)}")
    for item in evidence:
        chunk = item.chunk
        print(
            f"\n[{item.citation_id}] score={item.score:.4f} | page={chunk.page_number} "
            f"| chunk={chunk.chunk_index}"
        )
        print(f"Title: {chunk.title}")
        print(f"Paper ID: {chunk.paper_id or '(unversioned input)'}")
        print(f"Section: {chunk.section_title or '(unresolved)'}")
        print(f"Chunking: {chunk.chunking_version}")
        print(f"Chunk ID: {chunk.chunk_id}")
        print(f"Source: {chunk.source_path}")
        print(f"Evidence:\n{chunk.text}")


def _print_prompt(question: str, evidence: Sequence[RetrievedChunk]) -> None:
    print("===== SYSTEM PROMPT =====")
    print(SYSTEM_PROMPT)
    print("\n===== USER PROMPT =====")
    print(build_user_prompt(question, evidence))


def _print_answer(answer: Answer) -> None:
    print(answer.text)
    print("\nSources:")
    for citation in answer.citations:
        print(
            f"[{citation.citation_id}] {citation.title}, page {citation.page_number} "
            f"(score={citation.retrieval_score:.4f})\n    {citation.source_path}"
        )


def _print_agent_trace(result: AgentResult) -> None:
    plan = result.plan
    print("\nAgent Plan:")
    print(f"  Type: {plan.question_type} | Tasks: {len(plan.tasks)} | Revision: {plan.revision}")
    for task in plan.tasks:
        print(f"  {task.task_id}: {task.query}")
        print(f"    Goal: {task.goal}")
    assessment = result.assessment
    print("\nEvidence Assessment:")
    print(
        f"  Sufficient: {assessment.sufficient} | "
        f"Distinct papers: {assessment.distinct_paper_count} | "
        f"Retries: {result.retry_count}"
    )
    print(f"  Reason: {assessment.reason}")
    print("\nAgent Trace:")
    for event in result.trace:
        details = ", ".join(f"{key}={value}" for key, value in event.details.items())
        print(
            f"  {event.sequence}. {event.node}: {event.outcome} "
            f"({event.latency_ms:.0f} ms){f' | {details}' if details else ''}"
        )


def _preview(text: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return f"{normalized[: limit - 3].rstrip()}..."


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _unit_float(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("value must be between 0 and 1")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _add_retrieval_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--retrieval-mode",
        type=RetrievalMode,
        choices=tuple(RetrievalMode),
        default=RetrievalMode.EVIDENCE,
        help="evidence uses Dense; discovery uses Dense + BM25 with RRF",
    )


if __name__ == "__main__":
    raise SystemExit(main())
