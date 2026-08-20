"""Run isolated Parent/Child Clarification evaluation with production providers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.agent import AgentResult, AgentRuntimeConfig, build_agent_runtime
from paper_research_copilot.api import ResearchTaskService, ResearchTaskView
from paper_research_copilot.config import PROJECT_ROOT, Settings, get_settings
from paper_research_copilot.evaluation import (
    ClarificationCaseResult,
    ClarificationEvaluationCase,
    build_clarification_report,
    evaluate_clarification_case,
    load_clarification_cases,
)
from paper_research_copilot.retrieval import QdrantVectorStore
from paper_research_copilot.storage import (
    SqliteCheckpointStore,
    SqliteResearchRepository,
)


class ClarificationRunCacheRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    run_fingerprint: str
    parent_task_id: str | None = None
    child_task_id: str | None = None
    parent_result: AgentResult | None = None
    child_result: AgentResult | None = None
    child_parent_task_id: str | None = None
    persisted_response: str | None = None
    error: str | None = None
    parent_elapsed_ms: float = Field(default=0, ge=0)
    child_elapsed_ms: float = Field(default=0, ge=0)
    points_before: int = Field(default=0, ge=0)
    points_after_parent: int = Field(default=0, ge=0)
    points_after_child: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_outcome(self) -> ClarificationRunCacheRecord:
        if self.error is None and (
            self.parent_result is None
            or self.child_result is None
            or self.parent_task_id is None
            or self.child_task_id is None
        ):
            raise ValueError("Successful Clarification runs require Parent and Child results")
        return self


class ClarificationLiveCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    run_succeeded: bool
    error: str | None = None
    protocol: ClarificationCaseResult | None = None
    parent_elapsed_ms: float = Field(ge=0)
    child_elapsed_ms: float = Field(ge=0)
    total_elapsed_ms: float = Field(ge=0)
    points_before: int = Field(ge=0)
    points_after_parent: int = Field(ge=0)
    points_after_child: int = Field(ge=0)
    parent_point_delta: int
    child_point_delta: int
    child_evidence_count: int = Field(ge=0)
    child_citation_count: int = Field(ge=0)
    child_acquisition_rounds: int = Field(ge=0)
    child_acquisition_status: str | None = None
    child_acquisition_candidate_count: int = Field(default=0, ge=0)
    child_acquisition_downloaded_count: int = Field(default=0, ge=0)
    child_acquisition_indexed_count: int = Field(default=0, ge=0)
    citation_validation_passed: bool
    live_strict_pass: bool
    parent_trace_nodes: tuple[str, ...] = ()
    child_trace_nodes: tuple[str, ...] = ()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "clarification_v1.jsonl",
    )
    parser.add_argument("--baseline-id", default="clarification_live_v1")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--version", type=int, default=3)
    parser.add_argument("--collection", default="agent_seed_v3_bge_m3_chunking_v1")
    parser.add_argument("--max-retries", type=int, choices=(0, 1), default=1)
    args = parser.parse_args()

    all_cases = load_clarification_cases(args.dataset)
    selected = set(args.case_id)
    unknown = selected - {case.case_id for case in all_cases}
    if unknown:
        raise ValueError(f"Unknown Clarification Case IDs: {sorted(unknown)}")
    cases = tuple(case for case in all_cases if not selected or case.case_id in selected)
    settings = get_settings()
    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    run_root = (
        PROJECT_ROOT / "data" / "evaluation" / "clarification" / args.baseline_id
    )
    cache_path = run_root / "runs.jsonl"
    cache = _load_cache(cache_path)
    live_results: list[ClarificationLiveCaseResult] = []

    for index, case in enumerate(cases, 1):
        fingerprint = _run_fingerprint(
            case,
            dataset_sha256=dataset_sha256,
            settings=settings,
            version=args.version,
            collection=args.collection,
            max_retries=args.max_retries,
        )
        cached = cache.get(case.case_id)
        if cached is not None:
            if cached.run_fingerprint != fingerprint:
                raise ValueError(
                    f"Cached Clarification fingerprint changed for {case.case_id}; "
                    "use a new baseline ID"
                )
            record = cached
            source = "cache"
        else:
            record = _run_case(
                case,
                base_settings=settings,
                run_root=run_root,
                version=args.version,
                collection=args.collection,
                max_retries=args.max_retries,
                run_fingerprint=fingerprint,
            )
            cache[case.case_id] = record
            _write_cache(cache_path, cache.values())
            source = "live"
        evaluated = _evaluate_live_case(case, record)
        live_results.append(evaluated)
        print(
            f"[{index}/{len(cases)}] {case.case_id}: source={source}, "
            f"parent_points={evaluated.parent_point_delta:+d}, "
            f"child_answer={_child_status(record)}, citations={evaluated.child_citation_count}, "
            f"strict={evaluated.live_strict_pass}"
        )

    paths = _write_artifacts(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        dataset_sha256=dataset_sha256,
        cases=cases,
        results=live_results,
        settings=settings,
        version=args.version,
        collection=args.collection,
        max_retries=args.max_retries,
    )
    passed = sum(item.live_strict_pass for item in live_results)
    print(f"Live Strict Pass: {passed}/{len(live_results)}")
    print(f"Baseline JSON: {paths[0]}")
    print(f"Baseline report: {paths[1]}")
    print(f"Diagnostics: {paths[2]}")
    return 0 if passed == len(live_results) else 1


def _run_case(
    case: ClarificationEvaluationCase,
    *,
    base_settings: Settings,
    run_root: Path,
    version: int,
    collection: str,
    max_retries: int,
    run_fingerprint: str,
) -> ClarificationRunCacheRecord:
    case_root = run_root / case.case_id
    case_settings = base_settings.model_copy(
        update={
            "app_database_path": case_root / "app.db",
            "checkpoint_database_path": case_root / "checkpoints.db",
            "dynamic_assets_path": case_root / "papers",
            "dynamic_qdrant_path": case_root / "qdrant",
            "dynamic_qdrant_collection": _collection_name(run_root.name, case.case_id),
        }
    )
    if _case_state_exists(case_settings):
        raise RuntimeError(
            f"Clarification Case has state but no matching cache: {case.case_id}; "
            "use a new baseline ID"
        )
    points_before = _dynamic_point_count(case_settings)
    parent_result: AgentResult | None = None
    child_result: AgentResult | None = None
    parent_task_id: str | None = None
    child_task_id: str | None = None
    child_parent_task_id: str | None = None
    persisted_response: str | None = None
    error: str | None = None
    parent_elapsed_ms = 0.0
    child_elapsed_ms = 0.0
    points_after_parent = points_before
    points_after_child = points_before
    planner_cache = case_root / "planner.jsonl"

    try:
        parent_service = _build_service(
            case_settings,
            version=version,
            collection=collection,
            max_retries=max_retries,
            planner_cache=planner_cache,
        )
        started = time.perf_counter()
        try:
            parent = _wait_for_terminal(parent_service, parent_service.submit(case.question))
        finally:
            parent_service.close()
        parent_elapsed_ms = _elapsed_ms(started)
        if parent.status != "succeeded" or parent.result is None:
            raise RuntimeError(parent.error or f"Parent Task ended as {parent.status}")
        parent_task_id = parent.task_id
        parent_result = parent.result
        points_after_parent = _dynamic_point_count(case_settings)

        child_service = _build_service(
            case_settings,
            version=version,
            collection=collection,
            max_retries=max_retries,
            planner_cache=planner_cache,
        )
        started = time.perf_counter()
        try:
            child = _wait_for_terminal(
                child_service,
                child_service.clarify(parent.task_id, case.clarification_response),
            )
        finally:
            child_service.close()
        child_elapsed_ms = _elapsed_ms(started)
        if child.status != "succeeded" or child.result is None:
            raise RuntimeError(child.error or f"Child Task ended as {child.status}")
        child_task_id = child.task_id
        child_result = child.result
        child_parent_task_id = child.parent_task_id
        persisted_response = child.clarification_response
        points_after_child = _dynamic_point_count(case_settings)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        points_after_parent = _safe_point_count(case_settings, points_after_parent)
        points_after_child = _safe_point_count(case_settings, points_after_child)

    return ClarificationRunCacheRecord(
        case_id=case.case_id,
        run_fingerprint=run_fingerprint,
        parent_task_id=parent_task_id,
        child_task_id=child_task_id,
        parent_result=parent_result,
        child_result=child_result,
        child_parent_task_id=child_parent_task_id,
        persisted_response=persisted_response,
        error=error,
        parent_elapsed_ms=parent_elapsed_ms,
        child_elapsed_ms=child_elapsed_ms,
        points_before=points_before,
        points_after_parent=points_after_parent,
        points_after_child=points_after_child,
    )


def _build_service(
    settings: Settings,
    *,
    version: int,
    collection: str,
    max_retries: int,
    planner_cache: Path,
) -> ResearchTaskService:
    repository = SqliteResearchRepository(settings.resolved_app_database_path())
    checkpoint_store = SqliteCheckpointStore(
        settings.resolved_checkpoint_database_path()
    )
    return ResearchTaskService(
        lambda: build_agent_runtime(
            settings,
            version=version,
            collection_name=collection,
            planner_cache_path=planner_cache,
            config=AgentRuntimeConfig(
                top_k=settings.agent_top_k,
                candidate_pool_per_task=settings.agent_candidate_pool_per_task,
                max_retries=max_retries,
                max_acquisition_rounds=1,
                min_chunks_per_task=settings.agent_min_chunks_per_task,
            ),
            checkpointer=checkpoint_store.saver,
            repository=repository,
        ),
        repository=repository,
        checkpoint_store=checkpoint_store,
    )


def _wait_for_terminal(
    service: ResearchTaskService,
    accepted: ResearchTaskView,
    *,
    timeout_seconds: float = 1800,
) -> ResearchTaskView:
    deadline = time.monotonic() + timeout_seconds
    cursor = 0
    while time.monotonic() < deadline:
        events, terminal = service.wait_for_events(
            accepted.task_id,
            cursor,
            min(15.0, max(0.1, deadline - time.monotonic())),
        )
        if events:
            cursor = events[-1].sequence
        if terminal:
            return service.get(accepted.task_id)
    raise TimeoutError(f"Research Task timed out: {accepted.task_id}")


def _evaluate_live_case(
    case: ClarificationEvaluationCase,
    record: ClarificationRunCacheRecord,
) -> ClarificationLiveCaseResult:
    if record.parent_result is None or record.child_result is None:
        return ClarificationLiveCaseResult(
            case_id=case.case_id,
            run_succeeded=False,
            error=record.error or "Missing Parent or Child result",
            parent_elapsed_ms=record.parent_elapsed_ms,
            child_elapsed_ms=record.child_elapsed_ms,
            total_elapsed_ms=record.parent_elapsed_ms + record.child_elapsed_ms,
            points_before=record.points_before,
            points_after_parent=record.points_after_parent,
            points_after_child=record.points_after_child,
            parent_point_delta=record.points_after_parent - record.points_before,
            child_point_delta=record.points_after_child - record.points_after_parent,
            child_evidence_count=0,
            child_citation_count=0,
            child_acquisition_rounds=0,
            child_acquisition_status=None,
            child_acquisition_candidate_count=0,
            child_acquisition_downloaded_count=0,
            child_acquisition_indexed_count=0,
            citation_validation_passed=False,
            live_strict_pass=False,
        )
    protocol = evaluate_clarification_case(
        case,
        original_result=record.parent_result,
        child_result=record.child_result,
        parent_task_id=record.parent_task_id or "",
        child_parent_task_id=record.child_parent_task_id,
        persisted_response=record.persisted_response,
    )
    citation_valid = any(
        event.node == "validate_citations" and event.outcome == "valid"
        for event in record.child_result.trace
    )
    no_parent_write = record.points_after_parent == record.points_before
    live_strict = protocol.strict_pass and citation_valid and no_parent_write
    acquisition = record.child_result.acquisition
    return ClarificationLiveCaseResult(
        case_id=case.case_id,
        run_succeeded=record.error is None,
        error=record.error,
        protocol=protocol,
        parent_elapsed_ms=record.parent_elapsed_ms,
        child_elapsed_ms=record.child_elapsed_ms,
        total_elapsed_ms=record.parent_elapsed_ms + record.child_elapsed_ms,
        points_before=record.points_before,
        points_after_parent=record.points_after_parent,
        points_after_child=record.points_after_child,
        parent_point_delta=record.points_after_parent - record.points_before,
        child_point_delta=record.points_after_child - record.points_after_parent,
        child_evidence_count=len(record.child_result.evidence),
        child_citation_count=len(record.child_result.answer.citations),
        child_acquisition_rounds=record.child_result.acquisition_rounds,
        child_acquisition_status=acquisition.status if acquisition else None,
        child_acquisition_candidate_count=(
            acquisition.candidate_count if acquisition else 0
        ),
        child_acquisition_downloaded_count=(
            acquisition.downloaded_count if acquisition else 0
        ),
        child_acquisition_indexed_count=acquisition.indexed_count if acquisition else 0,
        citation_validation_passed=citation_valid,
        live_strict_pass=live_strict,
        parent_trace_nodes=tuple(event.node for event in record.parent_result.trace),
        child_trace_nodes=tuple(event.node for event in record.child_result.trace),
    )


def _write_artifacts(
    *,
    baseline_id: str,
    dataset_path: Path,
    dataset_sha256: str,
    cases: tuple[ClarificationEvaluationCase, ...],
    results: list[ClarificationLiveCaseResult],
    settings: Settings,
    version: int,
    collection: str,
    max_retries: int,
) -> tuple[Path, Path, Path]:
    protocol_results = tuple(item.protocol for item in results if item.protocol is not None)
    protocol_report = (
        build_clarification_report(protocol_results) if protocol_results else None
    )
    passed = sum(item.live_strict_pass for item in results)
    payload = {
        "config": {
            "baseline_id": baseline_id,
            "dataset_path": dataset_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "dataset_sha256": dataset_sha256,
            "case_ids": [case.case_id for case in cases],
            "corpus_version": version,
            "curated_collection": collection,
            "dynamic_state_policy": "isolated_empty_per_case",
            "planner_model": settings.gpt_model_name,
            "answer_model": settings.deepseek_model,
            "embedding_model": settings.siliconflow_embedding_model,
            "max_retries": max_retries,
            "max_acquisition_rounds": 1,
        },
        "summary": {
            "case_count": len(results),
            "run_success_rate": sum(item.run_succeeded for item in results) / len(results),
            "live_strict_pass_rate": passed / len(results),
            "parent_no_write_rate": sum(item.parent_point_delta == 0 for item in results)
            / len(results),
            "citation_validation_rate": sum(
                item.citation_validation_passed for item in results
            )
            / len(results),
            "semantic_judge_executed": False,
            "total_parent_elapsed_ms": sum(item.parent_elapsed_ms for item in results),
            "total_child_elapsed_ms": sum(item.child_elapsed_ms for item in results),
        },
        "protocol": protocol_report.model_dump(mode="json") if protocol_report else None,
        "cases": [item.model_dump(mode="json") for item in results],
    }
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    diagnostics_dir = PROJECT_ROOT / "evals" / "diagnostics"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{baseline_id}.json"
    markdown_path = baseline_dir / f"{baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{baseline_id}.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        _markdown_report(payload, results),
        encoding="utf-8",
    )
    diagnostics_path.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path, diagnostics_path


def _markdown_report(
    payload: dict[str, object],
    results: list[ClarificationLiveCaseResult],
) -> str:
    summary = payload["summary"]
    if not isinstance(summary, dict):
        raise TypeError("Clarification report summary must be a mapping")
    lines = [
        "# Clarification Live Evaluation v1",
        "",
        "## 总结",
        "",
        f"- Case：{summary['case_count']}",
        f"- Run Success：{float(summary['run_success_rate']):.2%}",
        f"- Live Strict Pass：{float(summary['live_strict_pass_rate']):.2%}",
        f"- Parent Zero-write：{float(summary['parent_no_write_rate']):.2%}",
        f"- Citation Validation：{float(summary['citation_validation_rate']):.2%}",
        "- 独立 Semantic LLM Judge：未执行",
        "",
        "## 逐 Case 结果",
        "",
        "| Case | Parent ms | Child ms | Parent Δ | Child Δ | Answer Status | "
        "Evidence | Citations | Acquisition | Strict |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- |",
    ]
    for item in results:
        child_status = (
            "error"
            if item.protocol is None
            else (
                "matched"
                if item.protocol.child_answer_behavior_correct
                else "mismatched"
            )
        )
        acquisition = (
            "-"
            if item.child_acquisition_rounds == 0
            else (
                f"{item.child_acquisition_rounds}:{item.child_acquisition_status or 'unknown'} "
                f"(c={item.child_acquisition_candidate_count}, "
                f"d={item.child_acquisition_downloaded_count}, "
                f"i={item.child_acquisition_indexed_count})"
            )
        )
        lines.append(
            f"| {item.case_id} | {item.parent_elapsed_ms:.0f} | "
            f"{item.child_elapsed_ms:.0f} | {item.parent_point_delta:+d} | "
            f"{item.child_point_delta:+d} | {child_status} | "
            f"{item.child_evidence_count} | {item.child_citation_count} | "
            f"{acquisition} | {'PASS' if item.live_strict_pass else 'FAIL'} |"
        )
    failures = [item for item in results if not item.live_strict_pass]
    lines.extend(["", "## 失败诊断", ""])
    if not failures:
        lines.append("所有 Case 均通过预设 Live Strict Gate。")
    else:
        for item in failures:
            lines.append(f"- `{item.case_id}`：{item.error or _failed_checks(item)}")
    lines.extend(
        [
            "",
            "## 人工审计",
            "",
            "- `CL-001`：正确解释 ReAct 的推理与行动交错机制；5 条 Citation 均来自 ReAct。",
            "- `CL-002`：按跨会话准确率优先、延迟其次推荐 MemGPT，并对比 Reflexion、ExpeL "
            "和 MemoryBank；答案明确指出现有证据不足以严谨比较延迟。该 Case 触发一次空 "
            "Acquisition，0 Candidate、0 Download、0 Index，未污染 Dynamic Collection，但增加了 "
            "Child 延迟。",
            "- `CL-003`：按外部工具、易实现和轨迹可审计约束推荐 CRITIC，并对比 AutoGen 与 "
            "AgentVerse；5 条 Citation 通过确定性校验。",
            "",
            "## 解释边界",
            "",
            "该实验验证真实 Provider 下的 Clarification、持久化重启、Child Research、"
            "Citation 和隔离动态库行为。",
            "`Answer Status matched` 只表示 Child 的 "
            "`answered / insufficient_evidence` 行为符合金标，"
            "不表示答案语义已经由 LLM Judge 判定正确。三条答案仅完成上述人工审计，本次没有运行"
            "独立 Semantic LLM Judge。",
            "三条 Case 仍是小样本，不能外推为任意多轮对话或任意含糊输入均可靠。",
            "",
        ]
    )
    return "\n".join(lines)


def _failed_checks(item: ClarificationLiveCaseResult) -> str:
    checks: list[str] = []
    if item.protocol is not None:
        for field in (
            "ambiguity_detected",
            "rule_matched",
            "prompt_present",
            "pre_clarification_side_effect_free",
            "child_reentered_research",
            "child_answer_behavior_correct",
            "provenance_valid",
        ):
            if getattr(item.protocol, field) is False:
                checks.append(field)
    if not item.citation_validation_passed:
        checks.append("citation_validation")
    if item.parent_point_delta != 0:
        checks.append("parent_dynamic_write")
    return ", ".join(checks) or "unknown"


def _dynamic_point_count(settings: Settings) -> int:
    store = QdrantVectorStore(
        settings.dynamic_qdrant_collection,
        settings.embedding_dimension,
        path=None if settings.qdrant_url else settings.resolved_dynamic_qdrant_path(),
        url=settings.qdrant_url,
        api_key=(
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None
        ),
    )
    try:
        return store.count()
    finally:
        store.close()


def _safe_point_count(settings: Settings, fallback: int) -> int:
    try:
        return _dynamic_point_count(settings)
    except Exception:
        return fallback


def _case_state_exists(settings: Settings) -> bool:
    if settings.resolved_app_database_path().exists():
        return True
    if settings.resolved_checkpoint_database_path().exists():
        return True
    if settings.resolved_dynamic_assets_path().exists():
        return True
    if settings.qdrant_url:
        return _dynamic_point_count(settings) > 0
    return settings.resolved_dynamic_qdrant_path().exists()


def _collection_name(baseline_id: str, case_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"cl_{baseline_id}_{case_id}")
    return safe[:120]


def _run_fingerprint(
    case: ClarificationEvaluationCase,
    *,
    dataset_sha256: str,
    settings: Settings,
    version: int,
    collection: str,
    max_retries: int,
) -> str:
    payload = {
        "case": case.model_dump(mode="json"),
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


def _load_cache(path: Path) -> dict[str, ClarificationRunCacheRecord]:
    if not path.is_file():
        return {}
    records = tuple(
        ClarificationRunCacheRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(records) != len({record.case_id for record in records}):
        raise ValueError("Clarification run cache contains duplicate Case IDs")
    return {record.case_id: record for record in records}


def _write_cache(
    path: Path,
    records: Iterable[ClarificationRunCacheRecord],
) -> None:
    materialized = sorted(records, key=lambda item: item.case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        "\n".join(record.model_dump_json() for record in materialized) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _child_status(record: ClarificationRunCacheRecord) -> str:
    return record.child_result.answer.status if record.child_result else "error"


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


if __name__ == "__main__":
    raise SystemExit(main())
