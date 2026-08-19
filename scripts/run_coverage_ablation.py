"""Compare global retrieval with query-decomposed, coverage-preserving retrieval."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.evaluation import (
    AnswerCaseResult,
    CachedAnswerJudge,
    StabilityAnswerRecord,
    StabilitySample,
    build_stability_config,
    build_stability_report,
    load_answer_cache,
    load_answer_evaluation_cases,
    run_answer_evaluation,
    run_judge_evaluation,
    write_answer_cache,
)
from paper_research_copilot.evaluation.answer_datasets import AnswerEvaluationCase
from paper_research_copilot.evaluation.judge_prompts import JUDGE_PROMPT_VERSION
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import (
    OpenAICompatibleChatProvider,
    SiliconFlowRerankerProvider,
)
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.reporting.prompts import ANSWER_PROMPT_VERSION
from paper_research_copilot.retrieval import (
    QUERY_DECOMPOSITION_PROMPT_VERSION,
    CachedQueryDecomposer,
    CoverageAwareRetriever,
    RetrievalMode,
    find_decomposition_alias_leaks,
)

DEFAULT_CASE_IDS = ("AE-016", "AE-017", "AE-018")

BASELINE_VARIANTS = {
    "answer_hybrid_rrf_v1": (PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_v1.jsonl"),
    "answer_hybrid_rrf_rerank_v1": (
        PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_rerank_v1.jsonl"
    ),
}

COVERAGE_VARIANTS = {
    "answer_coverage_hybrid_v1": False,
    "answer_coverage_hybrid_rerank_v1": True,
}

VARIANT_LABELS = {
    "answer_hybrid_rrf_v1": "Hybrid RRF",
    "answer_hybrid_rrf_rerank_v1": "Hybrid + Global Reranker",
    "answer_coverage_hybrid_v1": "Decomposition + Hybrid + Coverage",
    "answer_coverage_hybrid_rerank_v1": (
        "Decomposition + Hybrid + Per-subquery Reranker + Coverage"
    ),
}


class _FrozenEvidenceRetriever:
    def __init__(self, evidence: tuple[RetrievedChunk, ...]) -> None:
        self._evidence = evidence

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self._evidence[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--collection", default="agent_seed_v2_bge_m3_chunking_v1")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-pool-per-query", type=int, default=30)
    parser.add_argument("--baseline-id", default="coverage_aware_ablation_v1")
    parser.add_argument(
        "--decomposition-cache",
        type=Path,
        default=(
            PROJECT_ROOT
            / "evals"
            / "query_decompositions"
            / "answer_cross_paper_v1_deepseek-v4-flash.jsonl"
        ),
    )
    parser.add_argument(
        "--answer-cache",
        type=Path,
        default=(PROJECT_ROOT / "evals" / "stability" / "coverage_aware_answer_v1.jsonl"),
    )
    parser.add_argument(
        "--baseline-stability-results",
        type=Path,
        default=(PROJECT_ROOT / "evals" / "results" / "answer_generation_observability_v2.jsonl"),
    )
    args = parser.parse_args()
    if args.repetitions < 2:
        raise ValueError("Coverage stability evaluation requires at least two repetitions")
    if min(args.top_k, args.candidate_pool_per_query) < 1:
        raise ValueError("Top-K and candidate pool must be positive")

    selected_ids = tuple(args.case_id or DEFAULT_CASE_IDS)
    all_cases = load_answer_evaluation_cases(args.dataset)
    cases_by_id = {case.case_id: case for case in all_cases}
    unknown_ids = set(selected_ids) - cases_by_id.keys()
    if unknown_ids:
        raise ValueError(f"Unknown coverage Case IDs: {sorted(unknown_ids)}")
    cases = tuple(cases_by_id[case_id] for case_id in selected_ids)
    if any(case.question_type != "cross_paper" for case in cases):
        raise ValueError("Coverage ablation only accepts cross_paper cases")

    settings = get_settings()
    llm_url, llm_key = settings.require_llm_credentials()
    relay_url, relay_key = settings.require_relay_credentials()
    siliconflow_url, siliconflow_key = settings.require_siliconflow_credentials()
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

    decomposition_provider = OpenAICompatibleChatProvider(
        base_url=llm_url,
        api_key=llm_key,
        model=settings.deepseek_model,
        max_tokens=800,
    )
    decomposer = CachedQueryDecomposer(
        decomposition_provider,
        model=settings.deepseek_model,
        cache_path=args.decomposition_cache,
        sub_query_count=2,
        retry_attempts=3,
    )
    for index, case in enumerate(cases, start=1):
        sub_queries = decomposer.decompose(case.question)
        print(f"[{index}/{len(cases)}] {case.case_id} decomposition: {sub_queries}")
    decomposition_records = tuple(decomposer.record_for(case.question) for case in cases)
    leaks = find_decomposition_alias_leaks(decomposition_records, aliases)
    if leaks:
        raise ValueError(f"Query decompositions contain forbidden Corpus aliases: {leaks}")
    print("Query decomposition alias audit passed")

    baseline_samples = _load_baseline_samples(
        args.baseline_stability_results,
        selected_ids,
        args.repetitions,
    )
    retrieval_diagnostics = _load_baseline_retrieval_diagnostics(cases)
    answer_cache = load_answer_cache(args.answer_cache)
    new_samples: list[StabilitySample] = []

    answer_generator = AnswerGenerator(
        OpenAICompatibleChatProvider(
            base_url=llm_url,
            api_key=llm_key,
            model=settings.deepseek_model,
            max_tokens=settings.answer_max_tokens,
        )
    )
    reranker_provider = SiliconFlowRerankerProvider(
        siliconflow_url,
        siliconflow_key,
        settings.siliconflow_reranker_model,
    )
    runtime = build_retrieval_runtime(settings, args.collection)
    try:
        chunks_by_id = {chunk.chunk_id: chunk for chunk in runtime.vector_store.list_chunks()}
        evidence_text = {chunk_id: chunk.text for chunk_id, chunk in chunks_by_id.items()}
        hybrid = runtime.retriever_for(RetrievalMode.DISCOVERY)
        for variant_id, uses_reranker in COVERAGE_VARIANTS.items():
            coverage_retriever = CoverageAwareRetriever(
                hybrid,
                decomposer,
                reranker=reranker_provider if uses_reranker else None,
                candidate_pool_per_query=args.candidate_pool_per_query,
            )
            judge = CachedAnswerJudge(
                OpenAICompatibleChatProvider(
                    base_url=relay_url,
                    api_key=relay_key,
                    model=settings.gpt_model_name,
                    max_tokens=4000,
                ),
                model=settings.gpt_model_name,
                cache_path=(
                    PROJECT_ROOT
                    / "evals"
                    / "judges"
                    / f"coverage_v1_{variant_id}_{settings.gpt_model_name}.jsonl"
                ),
                retry_attempts=3,
            )
            retrieval_diagnostics[variant_id] = {}
            for case_index, case in enumerate(cases, start=1):
                evidence = coverage_retriever.retrieve(case.question, args.top_k)
                trace = coverage_retriever.trace_for(case.question)
                retrieval_diagnostics[variant_id][case.case_id] = _coverage_diagnostic(
                    case,
                    evidence,
                    trace=asdict(trace),
                )
                print(
                    f"[{variant_id} {case_index}/{len(cases)}] retrieval: "
                    f"quota={trace.selected_counts}, total={trace.total_latency_ms:.0f}ms"
                )
                for repetition in range(1, args.repetitions + 1):
                    cache_key = (variant_id, case.case_id, repetition)
                    cached_answer = answer_cache.get(cache_key)
                    if cached_answer is None:
                        answer_result = run_answer_evaluation(
                            _FrozenEvidenceRetriever(evidence),
                            answer_generator,
                            (case,),
                            top_k=args.top_k,
                        )[0]
                        cached_answer = StabilityAnswerRecord(
                            baseline_id=variant_id,
                            case_id=case.case_id,
                            repetition=repetition,
                            result=answer_result,
                        )
                        answer_cache[cache_key] = cached_answer
                        write_answer_cache(args.answer_cache, tuple(answer_cache.values()))
                        answer_source = "llm"
                    else:
                        answer_result = cached_answer.result
                        answer_source = "cache"
                    judged = run_judge_evaluation(
                        judge,
                        (case,),
                        (answer_result,),
                        evidence_text_by_chunk_id=evidence_text,
                        cache_key_by_case_id={
                            case.case_id: f"{variant_id}:{case.case_id}:r{repetition}"
                        },
                    )[0]
                    new_samples.append(
                        StabilitySample(
                            baseline_id=variant_id,
                            case_id=case.case_id,
                            repetition=repetition,
                            answer=answer_result,
                            judge=judged,
                        )
                    )
                    print(
                        f"  r{repetition}: answer={answer_source}/"
                        f"{answer_result.answer_status}, judge={judged.source}, "
                        f"C/F/CC={judged.decision.correctness.score}/"
                        f"{judged.decision.faithfulness.score}/"
                        f"{judged.decision.citation_completeness.score}"
                    )
    finally:
        runtime.close()

    all_samples = (*baseline_samples, *new_samples)
    config = build_stability_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        case_ids=selected_ids,
        repetitions=args.repetitions,
        answer_model=settings.deepseek_model,
        answer_prompt_version=ANSWER_PROMPT_VERSION,
        judge_model=settings.gpt_model_name,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        project_root=PROJECT_ROOT,
    ).model_copy(
        update={
            "evidence_policy": (
                "frozen_top10_per_variant; coverage variants use two leaked-name-audited "
                "sub-queries with round-robin merge"
            )
        }
    )
    report = build_stability_report(all_samples, config)
    diagnostics = _build_retrieval_report(
        cases,
        retrieval_diagnostics,
        decomposition_records=decomposition_records,
        leaks=leaks,
        top_k=args.top_k,
    )
    _write_artifacts(args.baseline_id, report, diagnostics, all_samples)
    print(f"Report: {PROJECT_ROOT / 'evals' / 'baselines' / f'{args.baseline_id}.md'}")
    return 0


def _load_baseline_samples(
    path: Path,
    case_ids: tuple[str, ...],
    repetitions: int,
) -> tuple[StabilitySample, ...]:
    allowed_variants = set(BASELINE_VARIANTS)
    samples = tuple(
        sample
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for sample in (StabilitySample.model_validate_json(line),)
        if sample.baseline_id in allowed_variants and sample.case_id in case_ids
    )
    expected = len(allowed_variants) * len(case_ids) * repetitions
    if len(samples) != expected:
        raise ValueError(f"Expected {expected} reusable Baseline samples, found {len(samples)}")
    return samples


def _load_baseline_retrieval_diagnostics(
    cases: tuple[AnswerEvaluationCase, ...],
) -> dict[str, dict[str, dict[str, Any]]]:
    case_ids = {case.case_id for case in cases}
    cases_by_id = {case.case_id: case for case in cases}
    diagnostics: dict[str, dict[str, dict[str, Any]]] = {}
    for variant_id, path in BASELINE_VARIANTS.items():
        results = tuple(
            result
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for result in (AnswerCaseResult.model_validate_json(line),)
            if result.case_id in case_ids
        )
        if len(results) != len(cases):
            raise ValueError(f"{variant_id} does not contain every selected retrieval Case")
        diagnostics[variant_id] = {
            result.case_id: _evaluated_evidence_diagnostic(
                cases_by_id[result.case_id],
                result,
            )
            for result in results
        }
    return diagnostics


def _evaluated_evidence_diagnostic(
    case: AnswerEvaluationCase,
    result: AnswerCaseResult,
) -> dict[str, Any]:
    evidence = [
        {
            "rank": item.rank,
            "chunk_id": item.chunk_id,
            "paper_id": item.paper_id,
            "page_number": item.page_number,
            "title": item.title,
        }
        for item in result.evidence
    ]
    return {
        **_coverage_metrics(case, evidence),
        "evidence": evidence,
        "trace": {"total_latency_ms": result.retrieval_latency_ms},
    }


def _coverage_diagnostic(
    case: AnswerEvaluationCase,
    evidence: tuple[RetrievedChunk, ...],
    *,
    trace: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "rank": rank,
            "chunk_id": item.chunk.chunk_id,
            "paper_id": item.chunk.paper_id,
            "page_number": item.chunk.page_number,
            "title": item.chunk.title,
        }
        for rank, item in enumerate(evidence, start=1)
    ]
    return {**_coverage_metrics(case, rows), "evidence": rows, "trace": trace}


def _coverage_metrics(
    case: AnswerEvaluationCase,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    retrieved_papers = {item["paper_id"] for item in evidence if item["paper_id"]}
    target_hits = {
        relevant.paper_id: {
            "paper": relevant.paper_id in retrieved_papers,
            "exact_page": any(
                item["paper_id"] == relevant.paper_id and item["page_number"] in relevant.pages
                for item in evidence
            ),
        }
        for relevant in case.relevant
    }
    paper_recall = sum(hit["paper"] for hit in target_hits.values()) / len(target_hits)
    exact_page_recall = sum(hit["exact_page"] for hit in target_hits.values()) / len(target_hits)
    return {
        "paper_recall_at_10": paper_recall,
        "exact_page_recall_at_10": exact_page_recall,
        "complete_papers_at_10": paper_recall == 1,
        "target_hits": target_hits,
    }


def _build_retrieval_report(
    cases: tuple[AnswerEvaluationCase, ...],
    diagnostics: dict[str, dict[str, dict[str, Any]]],
    *,
    decomposition_records: tuple[Any, ...],
    leaks: tuple[str, ...],
    top_k: int,
) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for variant_id, cases_by_id in diagnostics.items():
        case_values = tuple(cases_by_id[case.case_id] for case in cases)
        variants[variant_id] = {
            "paper_recall_at_10": _mean(item["paper_recall_at_10"] for item in case_values),
            "exact_page_recall_at_10": _mean(
                item["exact_page_recall_at_10"] for item in case_values
            ),
            "complete_papers_at_10": _mean(
                float(item["complete_papers_at_10"]) for item in case_values
            ),
            "cases": cases_by_id,
        }
    return {
        "top_k": top_k,
        "query_decomposition_prompt_version": QUERY_DECOMPOSITION_PROMPT_VERSION,
        "alias_leaks": leaks,
        "decompositions": [record.model_dump(mode="json") for record in decomposition_records],
        "variants": variants,
    }


def _write_artifacts(
    baseline_id: str,
    stability_report: Any,
    retrieval_report: dict[str, Any],
    samples: tuple[StabilitySample, ...],
) -> None:
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    results_dir = PROJECT_ROOT / "evals" / "results"
    diagnostics_dir = PROJECT_ROOT / "evals" / "diagnostics"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (baseline_dir / f"{baseline_id}.json").write_text(
        json.dumps(
            {
                "stability": stability_report.model_dump(mode="json"),
                "retrieval": retrieval_report,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (baseline_dir / f"{baseline_id}.md").write_text(
        _markdown(stability_report, retrieval_report),
        encoding="utf-8",
    )
    (results_dir / f"{baseline_id}.jsonl").write_text(
        "\n".join(sample.model_dump_json() for sample in samples) + "\n",
        encoding="utf-8",
    )
    (diagnostics_dir / "coverage_aware_retrieval_v1.json").write_text(
        json.dumps(retrieval_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _markdown(stability_report: Any, retrieval_report: dict[str, Any]) -> str:
    stability = {variant.baseline_id: variant for variant in stability_report.variants}
    variants = retrieval_report["variants"]
    lines = [
        "# Coverage-aware Retrieval 消融实验 v1",
        "",
        "## 实验设置",
        "",
        "- Cases：`AE-016`、`AE-017`、`AE-018`，均为匿名描述的跨论文比较题。",
        "- 每种策略冻结各自 Top-10 Evidence，Answer 重复生成 3 次。",
        "- Answer：`deepseek-v4-flash`；Semantic Judge：`gpt-5.5`。",
        "- Query Decomposition 禁止补充原问题未出现的论文名，并通过 Corpus alias 审计。",
        "",
        "## Retrieval Coverage",
        "",
        "| Strategy | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for variant_id in VARIANT_LABELS:
        item = variants[variant_id]
        lines.append(
            f"| {VARIANT_LABELS[variant_id]} | {item['paper_recall_at_10']:.2%} | "
            f"{item['exact_page_recall_at_10']:.2%} | "
            f"{item['complete_papers_at_10']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Answer Stability + LLM Judge",
            "",
            "| Strategy | Gen Success | Answerability | Correctness | Faithfulness | "
            "Citation Completeness | Strict Runs | Stable Cases | Truncation |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant_id in VARIANT_LABELS:
        item = stability[variant_id]
        lines.append(
            f"| {VARIANT_LABELS[variant_id]} | {item.generation_success_rate:.2%} | "
            f"{item.answerability_accuracy:.2%} | {item.correctness_mean:.2%} | "
            f"{item.faithfulness_mean:.2%} | {item.citation_completeness_mean:.2%} | "
            f"{item.strict_run_pass_rate:.2%} | {item.fully_stable_case_rate:.2%} | "
            f"{item.truncation_case_rate:.2%} |"
        )
    lines.extend(
        [
            "",
            "## 逐题 Coverage",
            "",
            "| Strategy | Case | Target Papers | Paper Recall | Exact Page Recall | Quota |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for variant_id in VARIANT_LABELS:
        for case_id, item in variants[variant_id]["cases"].items():
            hits = ", ".join(
                f"{paper_id}={'Y' if hit['paper'] else 'N'}"
                for paper_id, hit in item["target_hits"].items()
            )
            quota = item["trace"].get("selected_counts", "-")
            lines.append(
                f"| {VARIANT_LABELS[variant_id]} | {case_id} | {hits} | "
                f"{item['paper_recall_at_10']:.2%} | "
                f"{item['exact_page_recall_at_10']:.2%} | `{quota}` |"
            )
    lines.extend(
        [
            "",
            "## Coverage 额外延迟",
            "",
            "| Strategy | Case | Decomposition Generate | Cache Lookup | Hybrid Total | "
            "Reranker Total | Retrieval Total |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant_id in COVERAGE_VARIANTS:
        for case_id, item in variants[variant_id]["cases"].items():
            trace = item["trace"]
            lines.append(
                f"| {VARIANT_LABELS[variant_id]} | {case_id} | "
                f"{trace['decomposition_generation_latency_ms']:.0f} ms | "
                f"{trace['decomposition_latency_ms']:.0f} ms | "
                f"{sum(trace['hybrid_latency_ms']):.0f} ms | "
                f"{sum(trace['reranker_latency_ms']):.0f} ms | "
                f"{trace['total_latency_ms']:.0f} ms |"
            )
    lines.extend(
        [
            "",
            "## Query Decomposition 审计",
            "",
            f"- Alias leakage：`{retrieval_report['alias_leaks'] or '无'}`",
        ]
    )
    for record in retrieval_report["decompositions"]:
        lines.append(f"- `{record['question']}` -> `{record['sub_queries']}`")
    lines.extend(
        [
            "",
            "## 口径",
            "",
            "- Complete Papers@10 要求一个比较题的两篇目标论文都出现在 Top-10。",
            "- Exact Page Recall 使用人工标注的非穷举页码，因此是严格下界。",
            "- Strict Run 要求生成和 Answerability 正确，且 Judge 三维均不低于 3/4。",
            "- Baseline Answer/Judge 复用 Generation Observability v2；"
            "Coverage 两组为本实验新增调用。",
        ]
    )
    return "\n".join(lines) + "\n"


def _mean(values: Any) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


if __name__ == "__main__":
    raise SystemExit(main())
