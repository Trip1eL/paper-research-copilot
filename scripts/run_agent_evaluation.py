"""Compare fixed RAG, oracle routing, and the LangGraph Agent on frozen cases."""

import argparse
import time
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from paper_research_copilot.agent import AgentResult, build_agent_runtime
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.evaluation import (
    AgentEvaluationCase,
    AgentVariantCaseResult,
    AnswerCaseResult,
    CachedAnswerJudge,
    JudgeCaseResult,
    StabilitySample,
    build_agent_evaluation_config,
    build_agent_evaluation_report,
    build_agent_execution_metrics,
    build_answer_case_result,
    build_variant_case_result,
    load_agent_evaluation_cases,
    load_answer_evaluation_cases,
    run_judge_evaluation,
    write_agent_evaluation_artifacts,
)
from paper_research_copilot.ingestion import CorpusCatalogLoader
from paper_research_copilot.integrations import OpenAICompatibleChatProvider

DEFAULT_CASE_IDS = (
    "AE-001",
    "AE-007",
    "AE-014",
    "AE-016",
    "AE-017",
    "AE-018",
    "AE-019",
    "AE-020",
)
FIXED_SAMPLES = PROJECT_ROOT / "evals" / "results" / "answer_stability_v1.jsonl"
COVERAGE_SAMPLES = PROJECT_ROOT / "evals" / "results" / "coverage_aware_ablation_v1.jsonl"


class AgentRunCacheRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    result: AgentResult | None = None
    error: str | None = None
    elapsed_ms: float = 0

    @model_validator(mode="after")
    def validate_outcome(self) -> "AgentRunCacheRecord":
        if (self.result is None) == (self.error is None):
            raise ValueError("Agent cache record requires exactly one result or error")
        return self


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "agent_runtime_v1.jsonl",
    )
    parser.add_argument(
        "--answer-dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Evaluate every case in the selected Agent dataset",
    )
    parser.add_argument("--version", type=int, default=2)
    parser.add_argument("--collection", default="agent_seed_v2_bge_m3_chunking_v1")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--baseline-id", default="agent_runtime_v1")
    parser.add_argument(
        "--agent-cache",
        type=Path,
        default=PROJECT_ROOT / "data" / "agent" / "runtime_evaluation_v1.jsonl",
    )
    parser.add_argument(
        "--saved-answer-results",
        type=Path,
        default=None,
        help="Use saved AnswerCaseResult JSONL as the fixed-RAG comparison",
    )
    parser.add_argument(
        "--saved-judge-results",
        type=Path,
        default=None,
        help="Use saved JudgeCaseResult JSONL for the fixed-RAG comparison",
    )
    parser.add_argument("--saved-variant-id", default="fixed_hybrid_rrf")
    parser.add_argument("--judge-cache-tag", default="agent_runtime_v1")
    args = parser.parse_args()
    if args.top_k != 10:
        raise ValueError("Agent Evaluation v1 metrics are fixed at Top-10")
    if args.repetition < 1:
        raise ValueError("Frozen sample repetition must be positive")
    if args.all_cases and args.case_id:
        raise ValueError("Use either --all-cases or --case-id, not both")
    if bool(args.saved_answer_results) != bool(args.saved_judge_results):
        raise ValueError("Saved Answer and Judge results must be provided together")

    answer_cases = load_answer_evaluation_cases(args.answer_dataset)
    answer_by_id = {case.case_id: case for case in answer_cases}
    all_agent_cases = load_agent_evaluation_cases(args.dataset, answer_cases=answer_by_id)
    agent_by_id = {case.case_id: case for case in all_agent_cases}
    selected_ids = (
        tuple(agent_by_id)
        if args.all_cases
        else tuple(args.case_id or DEFAULT_CASE_IDS)
    )
    unknown = sorted(set(selected_ids) - agent_by_id.keys())
    if unknown:
        raise ValueError(f"Unknown Agent evaluation Case IDs: {unknown}")
    cases = tuple(agent_by_id[case_id] for case_id in selected_ids)

    comparison_notes: tuple[str, ...]
    if args.saved_answer_results is not None and args.saved_judge_results is not None:
        results = _build_saved_variant(
            cases,
            answers=_load_answer_results(args.saved_answer_results),
            judges=_load_judge_results(args.saved_judge_results),
            variant_id=args.saved_variant_id,
        )
        frozen_sources = (args.saved_answer_results, args.saved_judge_results)
        comparison_notes = (
            "Fixed-RAG uses saved Answer and Judge results from the selected corpus version.",
        )
    else:
        fixed_samples = _load_stability_samples(FIXED_SAMPLES)
        coverage_samples = _load_stability_samples(COVERAGE_SAMPLES)
        results = _build_frozen_variants(
            cases,
            fixed_samples=fixed_samples,
            coverage_samples=coverage_samples,
            repetition=args.repetition,
        )
        frozen_sources = (FIXED_SAMPLES, COVERAGE_SAMPLES)
        comparison_notes = (
            f"Frozen variants use repetition {args.repetition} from prior stability runs.",
            "Oracle Route uses Coverage Hybrid RRF for answerable cross-paper comparisons and "
            "Hybrid RRF for single-paper or known unanswerable cases.",
        )

    settings = get_settings()
    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    corpus_aliases = tuple(
        alias
        for asset in catalog.papers
        for alias in (
            asset.spec.slug,
            asset.spec.title,
            asset.spec.title.partition(":")[0],
        )
    )
    live_cache = _load_agent_cache(args.agent_cache)
    relay_url, relay_key = settings.require_relay_credentials()
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
            / f"{args.judge_cache_tag}_langgraph_agent_{settings.gpt_model_name}.jsonl"
        ),
        retry_attempts=3,
    )
    runtime = build_agent_runtime(
        settings,
        version=args.version,
        collection_name=args.collection,
    )
    try:
        for index, case in enumerate(cases, start=1):
            cached = live_cache.get(case.case_id)
            if cached is None:
                started = time.perf_counter()
                try:
                    agent_result = runtime.run(case.question)
                    cache_record = AgentRunCacheRecord(
                        case_id=case.case_id,
                        result=agent_result,
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    )
                except Exception as exc:
                    agent_result = None
                    cache_record = AgentRunCacheRecord(
                        case_id=case.case_id,
                        error=f"{type(exc).__name__}: {exc}",
                        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    )
                live_cache[case.case_id] = cache_record
                _write_agent_cache(args.agent_cache, live_cache.values())
                source = "live"
            else:
                agent_result = cached.result
                cache_record = cached
                source = "cache"
            answer_case = answer_by_id[case.case_id]
            if agent_result is None:
                answer_result = build_answer_case_result(
                    answer_case,
                    (),
                    None,
                    f"agent:{cache_record.error}",
                    None,
                    0,
                    cache_record.elapsed_ms,
                )
                judge_result = run_judge_evaluation(
                    judge,
                    (answer_case,),
                    (answer_result,),
                    evidence_text_by_chunk_id={},
                    cache_key_by_case_id={
                        case.case_id: f"{args.judge_cache_tag}:langgraph_agent:{case.case_id}:r1"
                    },
                )[0]
                results.append(
                    build_variant_case_result(
                        variant_id="langgraph_agent",
                        source="live_agent",
                        case=case,
                        answer=answer_result,
                        judge=judge_result,
                    )
                )
                print(
                    f"[langgraph_agent {index}/{len(cases)}] {case.case_id}: "
                    f"run={source}, error={cache_record.error}, judge={judge_result.source}:0/0/0"
                )
                continue
            execution = build_agent_execution_metrics(
                case,
                agent_result,
                corpus_aliases=corpus_aliases,
            )
            answer_result = build_answer_case_result(
                answer_case,
                agent_result.evidence,
                agent_result.answer,
                None,
                None,
                execution.retrieval_latency_ms,
                execution.answer_latency_ms,
            ).model_copy(update={"total_latency_ms": execution.workflow_latency_ms})
            judge_result = run_judge_evaluation(
                judge,
                (answer_case,),
                (answer_result,),
                evidence_text_by_chunk_id={
                    evidence.chunk_id: evidence.text for evidence in answer_result.evidence
                },
                cache_key_by_case_id={
                    case.case_id: f"{args.judge_cache_tag}:langgraph_agent:{case.case_id}:r1"
                },
            )[0]
            results.append(
                build_variant_case_result(
                    variant_id="langgraph_agent",
                    source="live_agent",
                    case=case,
                    answer=answer_result,
                    judge=judge_result,
                    execution=execution,
                )
            )
            print(
                f"[langgraph_agent {index}/{len(cases)}] {case.case_id}: "
                f"run={source}, route={execution.actual_question_type}, "
                f"tasks={execution.task_count}, retry={execution.retry_count}, "
                f"answer={answer_result.answer_status}, judge={judge_result.source}:"
                f"{judge_result.decision.correctness.score}/"
                f"{judge_result.decision.faithfulness.score}/"
                f"{judge_result.decision.citation_completeness.score}"
            )
    finally:
        runtime.close()

    config = build_agent_evaluation_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        case_ids=selected_ids,
        collection_name=args.collection,
        top_k=args.top_k,
        planner_model=settings.gpt_model_name,
        answer_model=settings.deepseek_model,
        judge_model=settings.gpt_model_name,
        frozen_sources=frozen_sources,
        project_root=PROJECT_ROOT,
        notes=comparison_notes
        + (
            "Agent workflow latency uses recorded generation latency even when Planner cache hits.",
        ),
    )
    report = build_agent_evaluation_report(results, config)
    json_path, markdown_path, diagnostics_path = write_agent_evaluation_artifacts(
        report,
        results,
        baseline_dir=PROJECT_ROOT / "evals" / "baselines",
        diagnostics_dir=PROJECT_ROOT / "evals" / "diagnostics",
    )
    print(f"Baseline JSON: {json_path}")
    print(f"Baseline report: {markdown_path}")
    print(f"Diagnostics: {diagnostics_path}")
    return 0


def _build_frozen_variants(
    cases: tuple[AgentEvaluationCase, ...],
    *,
    fixed_samples: dict[tuple[str, str, int], StabilitySample],
    coverage_samples: dict[tuple[str, str, int], StabilitySample],
    repetition: int,
) -> list[AgentVariantCaseResult]:
    results: list[AgentVariantCaseResult] = []
    fixed_variants = {
        "fixed_hybrid_rrf": "answer_hybrid_rrf_v1",
        "fixed_hybrid_rerank": "answer_hybrid_rrf_rerank_v1",
    }
    for variant_id, baseline_id in fixed_variants.items():
        for case in cases:
            sample = _require_sample(fixed_samples, baseline_id, case.case_id, repetition)
            results.append(
                build_variant_case_result(
                    variant_id=variant_id,
                    source="frozen_baseline",
                    case=case,
                    answer=sample.answer,
                    judge=sample.judge,
                )
            )
    for case in cases:
        if case.answerable and case.expected_question_type == "cross_paper":
            sample = _require_sample(
                coverage_samples,
                "answer_coverage_hybrid_v1",
                case.case_id,
                repetition,
            )
        else:
            sample = _require_sample(
                fixed_samples,
                "answer_hybrid_rrf_v1",
                case.case_id,
                repetition,
            )
        results.append(
            build_variant_case_result(
                variant_id="oracle_route",
                source="frozen_oracle",
                case=case,
                answer=sample.answer,
                judge=sample.judge,
            )
        )
    return results


def _build_saved_variant(
    cases: tuple[AgentEvaluationCase, ...],
    *,
    answers: dict[str, AnswerCaseResult],
    judges: dict[str, JudgeCaseResult],
    variant_id: str,
) -> list[AgentVariantCaseResult]:
    results: list[AgentVariantCaseResult] = []
    for case in cases:
        try:
            answer = answers[case.case_id]
            judge = judges[case.case_id]
        except KeyError as exc:
            raise LookupError(
                f"Missing saved fixed-RAG result for Agent case: {case.case_id}"
            ) from exc
        results.append(
            build_variant_case_result(
                variant_id=variant_id,
                source="frozen_baseline",
                case=case,
                answer=answer,
                judge=judge,
            )
        )
    return results


def _load_answer_results(path: Path) -> dict[str, AnswerCaseResult]:
    results = tuple(
        AnswerCaseResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {result.case_id: result for result in results}


def _load_judge_results(path: Path) -> dict[str, JudgeCaseResult]:
    results = tuple(
        JudgeCaseResult.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {result.case_id: result for result in results}


def _load_stability_samples(path: Path) -> dict[tuple[str, str, int], StabilitySample]:
    samples = tuple(
        StabilitySample.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {(sample.baseline_id, sample.case_id, sample.repetition): sample for sample in samples}


def _require_sample(
    samples: dict[tuple[str, str, int], StabilitySample],
    baseline_id: str,
    case_id: str,
    repetition: int,
) -> StabilitySample:
    key = (baseline_id, case_id, repetition)
    try:
        return samples[key]
    except KeyError as exc:
        raise LookupError(f"Missing frozen Agent evaluation sample: {key}") from exc


def _load_agent_cache(path: Path) -> dict[str, AgentRunCacheRecord]:
    if not path.is_file():
        return {}
    records = tuple(
        AgentRunCacheRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return {record.case_id: record for record in records}


def _write_agent_cache(path: Path, records: Iterable[AgentRunCacheRecord]) -> None:
    materialized = sorted(records, key=lambda item: item.case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(record.model_dump_json() for record in materialized) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
