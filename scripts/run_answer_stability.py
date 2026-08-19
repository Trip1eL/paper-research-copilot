"""Repeat answer generation over frozen baseline evidence and score every run."""

import argparse
import hashlib
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.evaluation import (
    AnswerCaseResult,
    AnswerEvaluationReport,
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
    write_stability_artifacts,
)
from paper_research_copilot.evaluation.judge_prompts import JUDGE_PROMPT_VERSION
from paper_research_copilot.integrations import OpenAICompatibleChatProvider
from paper_research_copilot.pipeline import build_retrieval_runtime
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.reporting.prompts import ANSWER_PROMPT_VERSION

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

DEFAULT_VARIANTS = {
    "answer_hybrid_rrf_v1": (
        PROJECT_ROOT / "evals" / "baselines" / "answer_hybrid_rrf_v1.json",
        PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_v1.jsonl",
    ),
    "answer_hybrid_rrf_rerank_v1": (
        PROJECT_ROOT / "evals" / "baselines" / "answer_hybrid_rrf_rerank_v1.json",
        PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_rerank_v1.jsonl",
    ),
}


class _FrozenEvidenceRetriever:
    def __init__(self, evidence: tuple[RetrievedChunk, ...]) -> None:
        self._evidence = evidence

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self._evidence[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--baseline-id", default="answer_stability_v1")
    parser.add_argument("--judge-cache-tag", default="stability")
    parser.add_argument(
        "--answer-cache",
        type=Path,
        default=PROJECT_ROOT / "evals" / "stability" / "answer_stability_v1.jsonl",
    )
    args = parser.parse_args()
    if args.repetitions < 2:
        raise ValueError("Stability evaluation requires at least two repetitions")

    selected_ids = tuple(args.case_id or DEFAULT_CASE_IDS)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Stability Case IDs must be unique")
    all_cases = load_answer_evaluation_cases(args.dataset)
    cases_by_id = {case.case_id: case for case in all_cases}
    unknown_ids = set(selected_ids) - cases_by_id.keys()
    if unknown_ids:
        raise ValueError(f"Unknown stability Case IDs: {sorted(unknown_ids)}")
    selected_cases = tuple(cases_by_id[case_id] for case_id in selected_ids)

    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    variants = {
        variant_id: _load_variant(baseline_path, results_path, dataset_sha256)
        for variant_id, (baseline_path, results_path) in DEFAULT_VARIANTS.items()
    }
    collections = {report.config.collection_name for report, _ in variants.values()}
    if len(collections) != 1:
        raise ValueError("Stability variants must use the same Qdrant Collection")

    settings = get_settings()
    llm_url, llm_key = settings.require_llm_credentials()
    relay_url, relay_key = settings.require_relay_credentials()
    answer_generator = AnswerGenerator(
        OpenAICompatibleChatProvider(
            base_url=llm_url,
            api_key=llm_key,
            model=settings.deepseek_model,
            max_tokens=settings.answer_max_tokens,
        )
    )
    answer_cache = load_answer_cache(args.answer_cache)
    runtime = build_retrieval_runtime(settings, collections.pop())
    samples: list[StabilitySample] = []
    try:
        chunks_by_id = {chunk.chunk_id: chunk for chunk in runtime.vector_store.list_chunks()}
        evidence_text = {chunk_id: chunk.text for chunk_id, chunk in chunks_by_id.items()}
        for variant_id, (_, baseline_results) in variants.items():
            baseline_by_case = {result.case_id: result for result in baseline_results}
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
                    / f"{args.judge_cache_tag}_{variant_id}_{settings.gpt_model_name}.jsonl"
                ),
                retry_attempts=3,
            )
            for case in selected_cases:
                frozen_evidence = _restore_evidence(
                    baseline_by_case[case.case_id],
                    chunks_by_id,
                )
                for repetition in range(1, args.repetitions + 1):
                    cache_key = (variant_id, case.case_id, repetition)
                    cached_answer = answer_cache.get(cache_key)
                    if cached_answer is None:
                        answer_result = run_answer_evaluation(
                            _FrozenEvidenceRetriever(frozen_evidence),
                            answer_generator,
                            (case,),
                            top_k=len(frozen_evidence),
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

                    judge_result = run_judge_evaluation(
                        judge,
                        (case,),
                        (answer_result,),
                        evidence_text_by_chunk_id=evidence_text,
                        cache_key_by_case_id={
                            case.case_id: f"{variant_id}:{case.case_id}:r{repetition}"
                        },
                    )[0]
                    samples.append(
                        StabilitySample(
                            baseline_id=variant_id,
                            case_id=case.case_id,
                            repetition=repetition,
                            answer=answer_result,
                            judge=judge_result,
                        )
                    )
                    print(
                        f"[{variant_id}] {case.case_id}/R{repetition}: "
                        f"answer={answer_source}:{answer_result.answer_status}, "
                        f"judge={judge_result.source}:"
                        f"{judge_result.decision.correctness.score}/"
                        f"{judge_result.decision.faithfulness.score}/"
                        f"{judge_result.decision.citation_completeness.score}"
                    )
    finally:
        runtime.close()

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
    )
    report = build_stability_report(samples, config)
    json_path, markdown_path, raw_path = write_stability_artifacts(
        report,
        samples,
        baseline_dir=PROJECT_ROOT / "evals" / "baselines",
        results_dir=PROJECT_ROOT / "evals" / "results",
    )
    print(f"Baseline JSON: {json_path}")
    print(f"Baseline report: {markdown_path}")
    print(f"Raw results: {raw_path}")
    return 0


def _load_variant(
    baseline_path: Path,
    results_path: Path,
    dataset_sha256: str,
) -> tuple[AnswerEvaluationReport, tuple[AnswerCaseResult, ...]]:
    report = AnswerEvaluationReport.model_validate_json(baseline_path.read_text(encoding="utf-8"))
    if report.config.dataset_sha256 != dataset_sha256:
        raise ValueError(f"Dataset SHA mismatch for {report.config.baseline_id}")
    results = tuple(
        AnswerCaseResult.model_validate_json(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(results) != report.case_count:
        raise ValueError(f"Result count mismatch for {report.config.baseline_id}")
    return report, results


def _restore_evidence(
    baseline_result: AnswerCaseResult,
    chunks_by_id: dict[str, PaperChunk],
) -> tuple[RetrievedChunk, ...]:
    missing = [
        evidence.chunk_id
        for evidence in baseline_result.evidence
        if evidence.chunk_id not in chunks_by_id
    ]
    if missing:
        raise LookupError(f"Frozen Evidence is missing from Qdrant: {missing}")
    return tuple(
        RetrievedChunk(
            citation_id=evidence.citation_id,
            score=evidence.score,
            chunk=chunks_by_id[evidence.chunk_id],
        )
        for evidence in baseline_result.evidence
    )


if __name__ == "__main__":
    raise SystemExit(main())
