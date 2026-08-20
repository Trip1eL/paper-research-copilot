"""Run isolated, resumable Open-world Agent evaluation cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from paper_research_copilot.agent import AgentResult, AgentRuntimeConfig, build_agent_runtime
from paper_research_copilot.config import PROJECT_ROOT, Settings, get_settings
from paper_research_copilot.evaluation import (
    OpenWorldEvaluationCase,
    build_open_world_config,
    build_open_world_report,
    evaluate_open_world_case,
    load_open_world_cases,
    write_open_world_artifacts,
)
from paper_research_copilot.retrieval.vector_store import QdrantVectorStore
from paper_research_copilot.storage import SqliteResearchRepository

DEFAULT_CASE_IDS = (
    "OW-IC-001",
    "OW-RC-001",
    "OW-UR-001",
    "OW-AM-001",
)


class OpenWorldRunCacheRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    run_fingerprint: str
    result: AgentResult | None = None
    error: str | None = None
    elapsed_ms: float
    points_before: int
    points_after: int

    @model_validator(mode="after")
    def validate_outcome(self) -> OpenWorldRunCacheRecord:
        if (self.result is None) == (self.error is None):
            raise ValueError("Open-world cache requires exactly one result or error")
        return self


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "open_world_v1.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--version", type=int, default=3)
    parser.add_argument("--collection", default="agent_seed_v3_bge_m3_chunking_v1")
    parser.add_argument("--baseline-id", default="open_world_v1_smoke")
    parser.add_argument(
        "--run-cache",
        type=Path,
        default=None,
        help="Reuse compatible AgentResult records across Baseline report IDs",
    )
    parser.add_argument("--max-retries", type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    if args.all_cases and args.case_id:
        raise ValueError("Use either --all-cases or --case-id, not both")

    all_cases = load_open_world_cases(args.dataset)
    by_id = {case.case_id: case for case in all_cases}
    selected_ids = tuple(by_id) if args.all_cases else tuple(args.case_id or DEFAULT_CASE_IDS)
    unknown = sorted(set(selected_ids) - by_id.keys())
    if unknown:
        raise ValueError(f"Unknown Open-world Case IDs: {unknown}")
    cases = tuple(by_id[case_id] for case_id in selected_ids)
    base_settings = get_settings()
    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    run_root = PROJECT_ROOT / "data" / "evaluation" / "open_world" / args.baseline_id
    cache_path = args.run_cache or run_root / "runs.jsonl"
    cache = _load_cache(cache_path)
    results = []

    for index, case in enumerate(cases, start=1):
        fingerprint = _run_fingerprint(
            case,
            dataset_sha256=dataset_sha256,
            settings=base_settings,
            version=args.version,
            collection=args.collection,
            max_retries=args.max_retries,
        )
        cached = cache.get(case.case_id)
        if cached is not None:
            if cached.run_fingerprint != fingerprint:
                raise ValueError(
                    f"Cached Open-world run fingerprint changed for {case.case_id}; "
                    "use a new baseline ID"
                )
            record = cached
            source = "cache"
        else:
            record = _run_case(
                case,
                base_settings=base_settings,
                run_root=run_root,
                version=args.version,
                collection=args.collection,
                max_retries=args.max_retries,
                run_fingerprint=fingerprint,
            )
            cache[case.case_id] = record
            _write_cache(cache_path, cache.values())
            source = "live"
        evaluated = evaluate_open_world_case(
            case,
            record.result,
            elapsed_ms=record.elapsed_ms,
            points_before=record.points_before,
            points_after=record.points_after,
            error=record.error,
        )
        results.append(evaluated)
        print(
            f"[{index}/{len(cases)}] {case.case_id}: source={source}, "
            f"acquire={evaluated.acquisition_rounds}, answer={evaluated.answer_status}, "
            f"dynamic={evaluated.dynamic_evidence_count}/{evaluated.evidence_count}, "
            f"points={evaluated.points_before}->{evaluated.points_after}, "
            f"strict={evaluated.strict_pass}"
        )

    config = build_open_world_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        cases=cases,
        corpus_version=args.version,
        curated_collection=args.collection,
        planner_model=base_settings.gpt_model_name,
        answer_model=base_settings.deepseek_model,
        max_retries=args.max_retries,
        max_acquisition_rounds=1,
        project_root=PROJECT_ROOT,
        notes=(
            "指标为确定性行为评估，不替代 Answer Semantic LLM Judge。",
            "Trigger Precision 将 Recoverable 视为唯一必须扩库类别；"
            "Unrecoverable 的一次有界搜索仍计入触发分母。",
            "运行缓存包含完整 AgentResult，位于 Git ignored 的 data/evaluation 目录。",
            f"Run Cache：{cache_path.as_posix()}",
        ),
    )
    report = build_open_world_report(results, config)
    paths = write_open_world_artifacts(
        report,
        results,
        baseline_dir=PROJECT_ROOT / "evals" / "baselines",
        diagnostics_dir=PROJECT_ROOT / "evals" / "diagnostics",
    )
    print(f"Strict Pass: {report.summary.strict_pass_rate:.2%}")
    print(f"Baseline JSON: {paths[0]}")
    print(f"Baseline report: {paths[1]}")
    print(f"Diagnostics: {paths[2]}")
    return 0


def _run_case(
    case: OpenWorldEvaluationCase,
    *,
    base_settings: Settings,
    run_root: Path,
    version: int,
    collection: str,
    max_retries: int,
    run_fingerprint: str,
) -> OpenWorldRunCacheRecord:
    case_root = run_root / case.case_id
    case_settings = base_settings.model_copy(
        update={
            "app_database_path": case_root / "app.db",
            "dynamic_assets_path": case_root / "papers",
            "dynamic_qdrant_path": case_root / "qdrant",
            "dynamic_qdrant_collection": _collection_name(run_root.name, case.case_id),
        }
    )
    if _case_state_exists(case_settings):
        raise RuntimeError(
            f"Open-world Case has state but no matching cache: {case.case_id}; "
            "use a new baseline ID"
        )
    points_before = _dynamic_point_count(case_settings)
    repository = SqliteResearchRepository(case_settings.resolved_app_database_path())
    runtime = None
    started = time.perf_counter()
    result = None
    error = None
    try:
        runtime = build_agent_runtime(
            case_settings,
            version=version,
            collection_name=collection,
            planner_cache_path=(
                PROJECT_ROOT
                / "data"
                / "agent"
                / f"open_world_v1_{case_settings.gpt_model_name}.jsonl"
            ),
            config=AgentRuntimeConfig(
                top_k=case_settings.agent_top_k,
                candidate_pool_per_task=case_settings.agent_candidate_pool_per_task,
                max_retries=max_retries,
                max_acquisition_rounds=1,
                min_chunks_per_task=case_settings.agent_min_chunks_per_task,
            ),
            repository=repository,
        )
        result = runtime.run(case.question, task_id=case.case_id)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if runtime is not None:
            runtime.close()
        repository.close()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    points_after = _dynamic_point_count(case_settings)
    return OpenWorldRunCacheRecord(
        case_id=case.case_id,
        run_fingerprint=run_fingerprint,
        result=result,
        error=error,
        elapsed_ms=elapsed_ms,
        points_before=points_before,
        points_after=points_after,
    )


def _dynamic_point_count(settings: Settings) -> int:
    store = QdrantVectorStore(
        settings.dynamic_qdrant_collection,
        settings.embedding_dimension,
        path=None if settings.qdrant_url else settings.resolved_dynamic_qdrant_path(),
        url=settings.qdrant_url,
        api_key=(
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        ),
    )
    try:
        return store.count()
    finally:
        store.close()


def _case_state_exists(settings: Settings) -> bool:
    if settings.resolved_app_database_path().exists():
        return True
    if settings.resolved_dynamic_assets_path().exists():
        return True
    if settings.qdrant_url:
        return _dynamic_point_count(settings) > 0
    return settings.resolved_dynamic_qdrant_path().exists()


def _collection_name(baseline_id: str, case_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"ow_{baseline_id}_{case_id}")
    return safe[:120]


def _run_fingerprint(
    case: OpenWorldEvaluationCase,
    *,
    dataset_sha256: str,
    settings: Settings,
    version: int,
    collection: str,
    max_retries: int,
) -> str:
    payload = {
        "case_id": case.case_id,
        "dataset_sha256": dataset_sha256,
        "version": version,
        "collection": collection,
        "planner_model": settings.gpt_model_name,
        "answer_model": settings.deepseek_model,
        "embedding_model": settings.siliconflow_embedding_model,
        "max_retries": max_retries,
        "max_acquisition_rounds": 1,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _load_cache(path: Path) -> dict[str, OpenWorldRunCacheRecord]:
    if not path.is_file():
        return {}
    records = tuple(
        OpenWorldRunCacheRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(records) != len({record.case_id for record in records}):
        raise ValueError("Open-world run cache contains duplicate Case IDs")
    return {record.case_id: record for record in records}


def _write_cache(path: Path, records: Iterable[OpenWorldRunCacheRecord]) -> None:
    materialized = sorted(records, key=lambda item: item.case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "\n".join(record.model_dump_json() for record in materialized) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
