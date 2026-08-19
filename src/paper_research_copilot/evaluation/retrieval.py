"""Deterministic metrics and reports for retrieval-only evaluation."""

import hashlib
import math
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.evaluation.datasets import RelevantPages, RetrievalDiagnosticCase


class Retriever(Protocol):
    def retrieve(self, question: str, top_k: int) -> tuple[RetrievedChunk, ...]: ...


@runtime_checkable
class QueryTraceProvider(Protocol):
    def queries_for(self, question: str) -> tuple[str, ...]: ...


class RetrievedCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1)
    score: float
    chunk_id: str
    paper_id: str | None
    page_number: int = Field(ge=1)
    section_title: str | None
    title: str


class RetrievalCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    question: str
    question_type: str
    difficulty: str
    evaluation_split: str | None = None
    retrieval_queries: tuple[str, ...] = ()
    relevant: tuple[RelevantPages, ...]
    latency_ms: float = Field(ge=0)
    candidates: tuple[RetrievedCandidate, ...]


class CutoffMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_hit_rate: float = Field(ge=0, le=1)
    paper_recall: float = Field(ge=0, le=1)
    complete_paper_coverage_rate: float = Field(ge=0, le=1)
    exact_page_hit_rate: float = Field(ge=0, le=1)
    exact_page_recall: float = Field(ge=0, le=1)
    complete_page_coverage_rate: float = Field(ge=0, le=1)
    same_page_redundancy_rate: float = Field(ge=0, le=1)


class MetricGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    group: str
    case_count: int = Field(ge=1)
    cutoffs: dict[int, CutoffMetrics]
    paper_mrr: float = Field(ge=0, le=1)
    exact_page_mrr: float = Field(ge=0, le=1)


class RetrievalEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_id: str
    corpus_version: int = Field(ge=1)
    collection_name: str
    embedding_model: str
    chunking_version: str
    retrieval_strategy: str
    strategy_parameters: dict[str, str | int | float | bool]
    top_k: int = Field(ge=1)
    cutoffs: tuple[int, ...]


class RetrievalEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: RetrievalEvaluationConfig
    case_count: int = Field(ge=1)
    first_query_latency_ms: float = Field(ge=0)
    subsequent_mean_latency_ms: float = Field(ge=0)
    mean_latency_ms: float = Field(ge=0)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    max_latency_ms: float = Field(ge=0)
    overall: MetricGroup
    by_question_type: tuple[MetricGroup, ...]
    by_difficulty: tuple[MetricGroup, ...]
    by_evaluation_split: tuple[MetricGroup, ...] = ()
    incomplete_paper_cases_at_top_k: tuple[str, ...]
    incomplete_page_cases_at_top_k: tuple[str, ...]


def run_retrieval_evaluation(
    retriever: Retriever,
    cases: Sequence[RetrievalDiagnosticCase],
    *,
    top_k: int,
    progress: Callable[[RetrievalCaseResult, int, int], None] | None = None,
) -> tuple[RetrievalCaseResult, ...]:
    results: list[RetrievalCaseResult] = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        evidence = retriever.retrieve(case.question, top_k)
        latency_ms = (time.perf_counter() - started) * 1000
        result = RetrievalCaseResult(
            case_id=case.case_id,
            question=case.question,
            question_type=case.question_type,
            difficulty=case.difficulty,
            evaluation_split=_evaluation_split(case),
            retrieval_queries=(
                retriever.queries_for(case.question)
                if isinstance(retriever, QueryTraceProvider)
                else ()
            ),
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
        results.append(result)
        if progress:
            progress(result, index, total)
    return tuple(results)


def build_evaluation_report(
    results: Sequence[RetrievalCaseResult],
    config: RetrievalEvaluationConfig,
) -> RetrievalEvaluationReport:
    if not results:
        raise ValueError("Cannot build an evaluation report without case results")
    cutoffs = tuple(sorted(set(config.cutoffs)))
    if not cutoffs or cutoffs[-1] > config.top_k or config.top_k not in cutoffs:
        raise ValueError("Evaluation cutoffs must include top_k and cannot exceed it")

    latencies = [result.latency_ms for result in results]
    overall = _metric_group("overall", results, cutoffs)
    by_question_type = tuple(
        _metric_group(
            question_type,
            [result for result in results if result.question_type == question_type],
            cutoffs,
        )
        for question_type in sorted({result.question_type for result in results})
    )
    by_difficulty = tuple(
        _metric_group(
            difficulty,
            [result for result in results if result.difficulty == difficulty],
            cutoffs,
        )
        for difficulty in sorted({result.difficulty for result in results})
    )
    split_names = sorted(
        {result.evaluation_split for result in results if result.evaluation_split is not None}
    )
    by_evaluation_split = tuple(
        _metric_group(
            split,
            [result for result in results if result.evaluation_split == split],
            cutoffs,
        )
        for split in split_names
    )
    return RetrievalEvaluationReport(
        config=config,
        case_count=len(results),
        first_query_latency_ms=latencies[0],
        subsequent_mean_latency_ms=round(
            sum(latencies[1:]) / len(latencies[1:]) if len(latencies) > 1 else latencies[0],
            2,
        ),
        mean_latency_ms=round(sum(latencies) / len(latencies), 2),
        p50_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_latency_ms=round(_percentile(latencies, 0.95), 2),
        max_latency_ms=round(max(latencies), 2),
        overall=overall,
        by_question_type=by_question_type,
        by_difficulty=by_difficulty,
        by_evaluation_split=by_evaluation_split,
        incomplete_paper_cases_at_top_k=tuple(
            result.case_id for result in results if _paper_recall(result, config.top_k) < 1
        ),
        incomplete_page_cases_at_top_k=tuple(
            result.case_id for result in results if _page_recall(result, config.top_k) < 1
        ),
    )


def _evaluation_split(case: RetrievalDiagnosticCase) -> str | None:
    if "anchor-v1" in case.tags:
        return "paired_anchor"
    challenge_tags = {"same-topic-distractor", "fine-grained", "challenge-v2"}
    if challenge_tags.intersection(case.tags):
        return "challenge"
    return None


def build_evaluation_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    corpus_id: str,
    corpus_version: int,
    collection_name: str,
    embedding_model: str,
    chunking_version: str,
    retrieval_strategy: str,
    strategy_parameters: dict[str, str | int | float | bool],
    top_k: int,
    cutoffs: Sequence[int],
    project_root: Path,
) -> RetrievalEvaluationConfig:
    return RetrievalEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=_sha256(dataset_path),
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        collection_name=collection_name,
        embedding_model=embedding_model,
        chunking_version=chunking_version,
        retrieval_strategy=retrieval_strategy,
        strategy_parameters=strategy_parameters,
        top_k=top_k,
        cutoffs=tuple(sorted(set(cutoffs))),
    )


def write_evaluation_artifacts(
    report: RetrievalEvaluationReport,
    results: Sequence[RetrievalCaseResult],
    *,
    baseline_dir: Path,
    results_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    raw_path = results_dir / f"{report.config.baseline_id}.jsonl"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    raw_path.write_text(
        "\n".join(result.model_dump_json() for result in results) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path, raw_path


def _metric_group(
    group: str,
    results: Sequence[RetrievalCaseResult],
    cutoffs: Sequence[int],
) -> MetricGroup:
    if not results:
        raise ValueError(f"Metric group has no cases: {group}")
    metrics = {
        cutoff: CutoffMetrics(
            paper_hit_rate=_mean(float(_paper_recall(result, cutoff) > 0) for result in results),
            paper_recall=_mean(_paper_recall(result, cutoff) for result in results),
            complete_paper_coverage_rate=_mean(
                float(_paper_recall(result, cutoff) == 1) for result in results
            ),
            exact_page_hit_rate=_mean(
                float(_page_recall(result, cutoff) > 0) for result in results
            ),
            exact_page_recall=_mean(_page_recall(result, cutoff) for result in results),
            complete_page_coverage_rate=_mean(
                float(_page_recall(result, cutoff) == 1) for result in results
            ),
            same_page_redundancy_rate=_mean(
                _same_page_redundancy(result, cutoff) for result in results
            ),
        )
        for cutoff in cutoffs
    }
    return MetricGroup(
        group=group,
        case_count=len(results),
        cutoffs=metrics,
        paper_mrr=_mean(_reciprocal_rank(result, exact_page=False) for result in results),
        exact_page_mrr=_mean(_reciprocal_rank(result, exact_page=True) for result in results),
    )


def _paper_recall(result: RetrievalCaseResult, cutoff: int) -> float:
    relevant_papers = {item.paper_id for item in result.relevant}
    retrieved_papers = {
        candidate.paper_id for candidate in result.candidates[:cutoff] if candidate.paper_id
    }
    return len(relevant_papers & retrieved_papers) / len(relevant_papers)


def _page_recall(result: RetrievalCaseResult, cutoff: int) -> float:
    candidates = result.candidates[:cutoff]
    covered = sum(
        any(
            candidate.paper_id == relevant.paper_id and candidate.page_number in relevant.pages
            for candidate in candidates
        )
        for relevant in result.relevant
    )
    return covered / len(result.relevant)


def _reciprocal_rank(result: RetrievalCaseResult, *, exact_page: bool) -> float:
    for candidate in result.candidates:
        for relevant in result.relevant:
            paper_matches = candidate.paper_id == relevant.paper_id
            page_matches = candidate.page_number in relevant.pages
            if paper_matches and (page_matches or not exact_page):
                return 1 / candidate.rank
    return 0.0


def _same_page_redundancy(result: RetrievalCaseResult, cutoff: int) -> float:
    candidates = result.candidates[:cutoff]
    if not candidates:
        return 0.0
    unique_pages = {(candidate.paper_id, candidate.page_number) for candidate in candidates}
    return 1 - (len(unique_pages) / len(candidates))


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 4)


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _markdown_report(
    report: RetrievalEvaluationReport,
    results: Sequence[RetrievalCaseResult],
) -> str:
    config = report.config
    lines = [
        f"# Retriever Baseline: {config.baseline_id}",
        "",
        f"- 评估日期：`{config.evaluated_on}`",
        f"- Dataset：`{config.dataset_path}`（{report.case_count} cases）",
        f"- Corpus：`{config.corpus_id}` / v{config.corpus_version}",
        f"- Collection：`{config.collection_name}`",
        f"- Embedding：`{config.embedding_model}`",
        f"- Chunking：`{config.chunking_version}`",
        f"- Strategy：`{config.retrieval_strategy}`",
        f"- Strategy parameters：`{config.strategy_parameters}`",
        f"- First query / subsequent mean：{report.first_query_latency_ms} / "
        f"{report.subsequent_mean_latency_ms} ms",
        f"- P50 / P95 / Max latency：{report.p50_latency_ms} / "
        f"{report.p95_latency_ms} / {report.max_latency_ms} ms",
        "",
        "## 总体指标",
        "",
        _metric_table(report.overall),
        "",
        f"- Paper MRR@{config.top_k}：{report.overall.paper_mrr:.4f}",
        f"- Exact Page MRR@{config.top_k}：{report.overall.exact_page_mrr:.4f}",
        "",
        "## 初步观察",
        "",
        *_observation_lines(report),
        "",
        "## 按问题类型",
        "",
        _group_table(report.by_question_type, config.top_k),
        "",
        "## 按难度",
        "",
        _group_table(report.by_difficulty, config.top_k),
        "",
        "## 按 Evaluation Split",
        "",
        _group_table(report.by_evaluation_split, config.top_k)
        if report.by_evaluation_split
        else "- 当前 Dataset 未定义 paired/challenge 分组。",
        "",
        "## 未完整覆盖的 Case",
        "",
        f"- Paper@{config.top_k}：{_case_list(report.incomplete_paper_cases_at_top_k)}",
        f"- Exact Page@{config.top_k}：{_case_list(report.incomplete_page_cases_at_top_k)}",
        "",
        "## 逐题 Top-1",
        "",
        "| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for result in results:
        top = result.candidates[0] if result.candidates else None
        paper_hit = _paper_recall(result, 1) > 0
        page_hit = _page_recall(result, 1) > 0
        lines.append(
            f"| {result.case_id} | {result.question_type} | "
            f"{top.paper_id if top else '-'} | {top.page_number if top else '-'} | "
            f"{top.score:.4f} | {paper_hit} | {page_hit} |"
            if top
            else f"| {result.case_id} | {result.question_type} | - | - | - | False | False |"
        )
    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "- Paper Recall 对跨论文问题按目标论文覆盖比例计算。",
            "- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。",
            "- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。",
            "- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。",
            "- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。",
            "",
        ]
    )
    return "\n".join(lines)


def _metric_table(group: MetricGroup) -> str:
    lines = [
        "| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | "
        "Exact Page Recall | Complete Pages | Same-page Redundancy |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cutoff, metrics in sorted(group.cutoffs.items()):
        lines.append(
            f"| {cutoff} | {metrics.paper_hit_rate:.2%} | {metrics.paper_recall:.2%} | "
            f"{metrics.complete_paper_coverage_rate:.2%} | "
            f"{metrics.exact_page_hit_rate:.2%} | {metrics.exact_page_recall:.2%} | "
            f"{metrics.complete_page_coverage_rate:.2%} | "
            f"{metrics.same_page_redundancy_rate:.2%} |"
        )
    return "\n".join(lines)


def _group_table(groups: Sequence[MetricGroup], cutoff: int) -> str:
    lines = [
        "| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | "
        "Paper MRR | Page MRR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in groups:
        metrics = group.cutoffs[cutoff]
        lines.append(
            f"| {group.group} | {group.case_count} | {metrics.paper_recall:.2%} | "
            f"{metrics.complete_paper_coverage_rate:.2%} | "
            f"{metrics.exact_page_recall:.2%} | {group.paper_mrr:.4f} | "
            f"{group.exact_page_mrr:.4f} |"
        )
    return "\n".join(lines)


def _case_list(case_ids: Sequence[str]) -> str:
    return ", ".join(case_ids) if case_ids else "无"


def _observation_lines(report: RetrievalEvaluationReport) -> list[str]:
    top_k = report.config.top_k
    top_metrics = report.overall.cutoffs[top_k]
    lines = [
        f"- Top-{top_k} Paper Recall 为 {top_metrics.paper_recall:.2%}；"
        f"完整覆盖率为 {top_metrics.complete_paper_coverage_rate:.2%}。",
        f"- Top-{top_k} Exact Page Recall 为 {top_metrics.exact_page_recall:.2%}；"
        "该指标受非穷举页码标注影响，是严格下界。",
        f"- Top-{top_k} Same-page Redundancy 为 {top_metrics.same_page_redundancy_rate:.2%}。",
    ]
    if 5 in report.overall.cutoffs and top_k > 5:
        at_five = report.overall.cutoffs[5]
        redundancy_delta = top_metrics.same_page_redundancy_rate - at_five.same_page_redundancy_rate
        lines.append(
            f"- 从 Top-5 增加到 Top-{top_k}，Paper Recall 变化 "
            f"{top_metrics.paper_recall - at_five.paper_recall:+.2%}，Exact Page Recall 变化 "
            f"{top_metrics.exact_page_recall - at_five.exact_page_recall:+.2%}，"
            f"同页冗余变化 {redundancy_delta:+.2%}。"
        )
    return lines
