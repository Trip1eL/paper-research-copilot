"""Agent-vs-fixed-RAG evaluation contracts and deterministic metrics."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.agent import AgentEvent, AgentResult, find_plan_alias_leaks
from paper_research_copilot.evaluation.answer import AnswerCaseResult
from paper_research_copilot.evaluation.answer_datasets import AnswerEvaluationCase
from paper_research_copilot.evaluation.datasets import RelevantPages
from paper_research_copilot.evaluation.judge import JudgeCaseResult

VariantSource = Literal["frozen_baseline", "frozen_oracle", "live_agent"]


class ExpectedTaskFacet(BaseModel):
    model_config = ConfigDict(frozen=True)

    facet_id: str = Field(pattern=r"^F[1-4]$")
    description: str = Field(min_length=3)
    match_any: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_aliases(self) -> "ExpectedTaskFacet":
        aliases = tuple(alias.strip().casefold() for alias in self.match_any)
        if any(not alias for alias in aliases):
            raise ValueError("Task-facet aliases must not be empty")
        if len(aliases) != len(set(aliases)):
            raise ValueError("Task-facet aliases must be unique")
        return self


class AgentEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^AE-[0-9]{3}$")
    question: str = Field(min_length=5)
    expected_question_type: Literal["single_paper", "cross_paper"]
    expected_task_count: int = Field(ge=1, le=4)
    expected_retrieval_strategy: Literal["hybrid_rrf", "coverage_hybrid_rrf"]
    expected_facets: tuple[ExpectedTaskFacet, ...] = Field(min_length=1, max_length=4)
    relevant: tuple[RelevantPages, ...] = ()
    should_retry: bool = False
    answerable: bool = True

    @model_validator(mode="after")
    def validate_route_contract(self) -> "AgentEvaluationCase":
        expected_tasks = 1 if self.expected_question_type == "single_paper" else None
        if expected_tasks is not None and self.expected_task_count != expected_tasks:
            raise ValueError("single_paper cases require one expected task")
        if self.expected_question_type == "cross_paper" and self.expected_task_count < 2:
            raise ValueError("cross_paper cases require at least two expected tasks")
        expected_strategy = (
            "hybrid_rrf" if self.expected_question_type == "single_paper" else "coverage_hybrid_rrf"
        )
        if self.expected_retrieval_strategy != expected_strategy:
            raise ValueError("Expected retrieval strategy must agree with question type")
        if self.answerable and not self.relevant:
            raise ValueError("Answerable Agent cases require relevant papers")
        if not self.answerable and self.relevant:
            raise ValueError("Unanswerable Agent cases must not declare relevant papers")
        return self


class RetrievalCoverageMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_recall_at_10: float | None = Field(default=None, ge=0, le=1)
    exact_page_recall_at_10: float | None = Field(default=None, ge=0, le=1)
    complete_papers_at_10: bool | None = None


class AgentExecutionMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    actual_question_type: Literal["single_paper", "cross_paper"]
    router_correct: bool
    task_count: int = Field(ge=1)
    task_count_correct: bool
    covered_facets: tuple[str, ...]
    task_coverage: float = Field(ge=0, le=1)
    retrieval_strategy: str
    retrieval_strategy_correct: bool
    title_leaks: tuple[str, ...]
    retry_count: int = Field(ge=0)
    revision_expected: bool
    revision_correct: bool
    citation_validation_passed: bool
    planning_latency_ms: float = Field(ge=0)
    retrieval_latency_ms: float = Field(ge=0)
    revision_latency_ms: float = Field(ge=0)
    answer_latency_ms: float = Field(ge=0)
    workflow_latency_ms: float = Field(ge=0)
    planner_input_tokens: int | None = Field(default=None, ge=0)
    planner_output_tokens: int | None = Field(default=None, ge=0)
    answer_input_tokens: int | None = Field(default=None, ge=0)
    answer_output_tokens: int | None = Field(default=None, ge=0)
    model_call_count: int = Field(ge=0)


class AgentVariantCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    case_id: str
    source: VariantSource
    answer: AnswerCaseResult
    judge: JudgeCaseResult
    retrieval: RetrievalCoverageMetrics
    execution: AgentExecutionMetrics | None = None
    strict_pass: bool
    workflow_latency_ms: float = Field(ge=0)
    answer_input_tokens: int | None = Field(default=None, ge=0)
    answer_output_tokens: int | None = Field(default=None, ge=0)
    judge_input_tokens: int | None = Field(default=None, ge=0)
    judge_output_tokens: int | None = Field(default=None, ge=0)
    model_call_count: int = Field(ge=0)


class AgentPlanningSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    router_accuracy: float = Field(ge=0, le=1)
    task_count_accuracy: float = Field(ge=0, le=1)
    task_coverage: float = Field(ge=0, le=1)
    title_leakage_rate: float = Field(ge=0, le=1)
    retrieval_strategy_accuracy: float = Field(ge=0, le=1)
    unnecessary_revision_rate: float = Field(ge=0, le=1)
    revision_recovery_rate: float | None = Field(default=None, ge=0, le=1)
    citation_validation_rate: float = Field(ge=0, le=1)
    p50_planning_latency_ms: float = Field(ge=0)
    p95_planning_latency_ms: float = Field(ge=0)


class AgentVariantSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    case_count: int = Field(ge=1)
    paper_recall_at_10: float = Field(ge=0, le=1)
    exact_page_recall_at_10: float = Field(ge=0, le=1)
    complete_papers_at_10: float = Field(ge=0, le=1)
    cross_paper_complete_papers_at_10: float = Field(ge=0, le=1)
    answerability_accuracy: float = Field(ge=0, le=1)
    unanswerable_refusal_rate: float = Field(ge=0, le=1)
    correctness: float = Field(ge=0, le=1)
    faithfulness: float = Field(ge=0, le=1)
    citation_completeness: float = Field(ge=0, le=1)
    strict_run_pass_rate: float = Field(ge=0, le=1)
    p50_workflow_latency_ms: float = Field(ge=0)
    p95_workflow_latency_ms: float = Field(ge=0)
    known_planner_input_tokens: int = Field(ge=0)
    known_planner_output_tokens: int = Field(ge=0)
    known_answer_input_tokens: int = Field(ge=0)
    known_answer_output_tokens: int = Field(ge=0)
    judge_input_tokens: int = Field(ge=0)
    judge_output_tokens: int = Field(ge=0)
    model_call_count: int = Field(ge=0)
    planning: AgentPlanningSummary | None = None


class AgentEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...]
    collection_name: str
    top_k: int = Field(ge=1)
    planner_model: str
    answer_model: str
    judge_model: str
    frozen_sources: tuple[str, ...]
    notes: tuple[str, ...] = ()


class AgentEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: AgentEvaluationConfig
    variants: tuple[AgentVariantSummary, ...]


def load_agent_evaluation_cases(
    path: Path,
    *,
    answer_cases: Mapping[str, AnswerEvaluationCase] | None = None,
) -> tuple[AgentEvaluationCase, ...]:
    cases = tuple(
        AgentEvaluationCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Agent evaluation dataset is empty")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Agent evaluation dataset contains duplicate Case IDs")
    if answer_cases is not None:
        unknown = sorted(set(case_ids) - answer_cases.keys())
        if unknown:
            raise ValueError(f"Agent dataset references unknown Answer cases: {unknown}")
        mismatches = [
            case.case_id
            for case in cases
            if case.question != answer_cases[case.case_id].question
            or case.answerable != answer_cases[case.case_id].answerable
            or case.relevant != answer_cases[case.case_id].relevant
        ]
        if mismatches:
            raise ValueError(f"Agent cases disagree with Answer dataset: {mismatches}")
    return cases


def build_agent_execution_metrics(
    case: AgentEvaluationCase,
    result: AgentResult,
    *,
    corpus_aliases: Iterable[str],
) -> AgentExecutionMetrics:
    plan_text = "\n".join(f"{task.query}\n{task.goal}" for task in result.plan.tasks).casefold()
    covered_facets = tuple(
        facet.facet_id
        for facet in case.expected_facets
        if any(alias.casefold() in plan_text for alias in facet.match_any)
    )
    retrieval_events = [event for event in result.trace if event.node == "retrieve_evidence"]
    strategy = str(retrieval_events[-1].details.get("strategy", "unknown"))
    planning_events = [event for event in result.trace if event.node == "plan_research"]
    revision_events = [event for event in result.trace if event.node == "revise_queries"]
    write_events = [event for event in result.trace if event.node == "write_report"]
    planning_latency = sum(_effective_planner_latency(event) for event in planning_events)
    revision_latency = sum(_effective_planner_latency(event) for event in revision_events)
    retrieval_latency = sum(event.latency_ms for event in retrieval_events)
    answer_latency = sum(event.latency_ms for event in write_events)
    validation_passed = any(
        event.node == "validate_citations" and event.outcome == "valid" for event in result.trace
    )
    answer_attempts = sum(_event_int(event, "answer_attempts") for event in write_events)
    planner_calls = len(planning_events) + len(revision_events)
    return AgentExecutionMetrics(
        actual_question_type=result.plan.question_type,
        router_correct=result.plan.question_type == case.expected_question_type,
        task_count=len(result.plan.tasks),
        task_count_correct=len(result.plan.tasks) == case.expected_task_count,
        covered_facets=covered_facets,
        task_coverage=len(covered_facets) / len(case.expected_facets),
        retrieval_strategy=strategy,
        retrieval_strategy_correct=strategy == case.expected_retrieval_strategy,
        title_leaks=find_plan_alias_leaks(result.plan, corpus_aliases),
        retry_count=result.retry_count,
        revision_expected=case.should_retry,
        revision_correct=(result.retry_count > 0) == case.should_retry,
        citation_validation_passed=validation_passed,
        planning_latency_ms=round(planning_latency, 2),
        retrieval_latency_ms=round(retrieval_latency, 2),
        revision_latency_ms=round(revision_latency, 2),
        answer_latency_ms=round(answer_latency, 2),
        workflow_latency_ms=round(
            planning_latency + retrieval_latency + revision_latency + answer_latency,
            2,
        ),
        planner_input_tokens=_sum_event_tokens(
            (*planning_events, *revision_events), "planner_input_tokens"
        ),
        planner_output_tokens=_sum_event_tokens(
            (*planning_events, *revision_events), "planner_output_tokens"
        ),
        answer_input_tokens=_sum_event_tokens(write_events, "answer_input_tokens"),
        answer_output_tokens=_sum_event_tokens(write_events, "answer_output_tokens"),
        model_call_count=planner_calls + answer_attempts,
    )


def build_retrieval_coverage(
    case: AgentEvaluationCase,
    answer: AnswerCaseResult,
) -> RetrievalCoverageMetrics:
    if not case.relevant:
        return RetrievalCoverageMetrics()
    evidence = answer.evidence[:10]
    paper_hits = [
        any(item.paper_id == relevant.paper_id for item in evidence) for relevant in case.relevant
    ]
    page_hits = [
        any(
            item.paper_id == relevant.paper_id and item.page_number in relevant.pages
            for item in evidence
        )
        for relevant in case.relevant
    ]
    return RetrievalCoverageMetrics(
        paper_recall_at_10=_mean(float(hit) for hit in paper_hits),
        exact_page_recall_at_10=_mean(float(hit) for hit in page_hits),
        complete_papers_at_10=all(paper_hits),
    )


def build_variant_case_result(
    *,
    variant_id: str,
    source: VariantSource,
    case: AgentEvaluationCase,
    answer: AnswerCaseResult,
    judge: JudgeCaseResult,
    execution: AgentExecutionMetrics | None = None,
) -> AgentVariantCaseResult:
    answer_input, answer_output, answer_calls = _answer_usage(answer)
    if execution is not None:
        answer_input = execution.answer_input_tokens
        answer_output = execution.answer_output_tokens
        model_calls = execution.model_call_count
        workflow_latency = execution.workflow_latency_ms
    else:
        model_calls = answer_calls
        workflow_latency = answer.total_latency_ms
    judge_calls = judge.attempts if judge.source != "deterministic" else 0
    return AgentVariantCaseResult(
        variant_id=variant_id,
        case_id=case.case_id,
        source=source,
        answer=answer,
        judge=judge,
        retrieval=build_retrieval_coverage(case, answer),
        execution=execution,
        strict_pass=_strict_pass(answer, judge),
        workflow_latency_ms=workflow_latency,
        answer_input_tokens=answer_input,
        answer_output_tokens=answer_output,
        judge_input_tokens=judge.usage.input_tokens,
        judge_output_tokens=judge.usage.output_tokens,
        model_call_count=model_calls + judge_calls,
    )


def build_agent_evaluation_report(
    results: Sequence[AgentVariantCaseResult],
    config: AgentEvaluationConfig,
) -> AgentEvaluationReport:
    if not results:
        raise ValueError("Cannot build an Agent evaluation report without results")
    by_variant: defaultdict[str, list[AgentVariantCaseResult]] = defaultdict(list)
    for result in results:
        by_variant[result.variant_id].append(result)
    expected = set(config.case_ids)
    for variant_id, samples in by_variant.items():
        actual = {sample.case_id for sample in samples}
        if actual != expected or len(samples) != len(expected):
            raise ValueError(
                f"Variant {variant_id} does not contain exactly the configured Agent cases"
            )
    return AgentEvaluationReport(
        config=config,
        variants=tuple(
            _build_variant_summary(variant_id, samples)
            for variant_id, samples in by_variant.items()
        ),
    )


def build_agent_evaluation_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    case_ids: Sequence[str],
    collection_name: str,
    top_k: int,
    planner_model: str,
    answer_model: str,
    judge_model: str,
    frozen_sources: Sequence[Path],
    project_root: Path,
    notes: Sequence[str] = (),
) -> AgentEvaluationConfig:
    return AgentEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        case_ids=tuple(case_ids),
        collection_name=collection_name,
        top_k=top_k,
        planner_model=planner_model,
        answer_model=answer_model,
        judge_model=judge_model,
        frozen_sources=tuple(
            path.resolve().relative_to(project_root.resolve()).as_posix() for path in frozen_sources
        ),
        notes=tuple(notes),
    )


def write_agent_evaluation_artifacts(
    report: AgentEvaluationReport,
    results: Sequence[AgentVariantCaseResult],
    *,
    baseline_dir: Path,
    diagnostics_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{report.config.baseline_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    diagnostics_path.write_text(
        json.dumps(
            [result.model_dump(mode="json") for result in results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path, diagnostics_path


def _build_variant_summary(
    variant_id: str,
    samples: Sequence[AgentVariantCaseResult],
) -> AgentVariantSummary:
    answerable = [sample for sample in samples if sample.answer.answerable]
    cross_paper = [sample for sample in answerable if sample.answer.question_type == "cross_paper"]
    unanswerable = [sample for sample in samples if not sample.answer.answerable]
    retrieval = [sample.retrieval for sample in answerable]
    executions = [sample.execution for sample in samples if sample.execution is not None]
    return AgentVariantSummary(
        variant_id=variant_id,
        case_count=len(samples),
        paper_recall_at_10=_mean_known(item.paper_recall_at_10 for item in retrieval),
        exact_page_recall_at_10=_mean_known(item.exact_page_recall_at_10 for item in retrieval),
        complete_papers_at_10=_mean(
            float(item.complete_papers_at_10 is True) for item in retrieval
        ),
        cross_paper_complete_papers_at_10=_mean(
            float(sample.retrieval.complete_papers_at_10 is True) for sample in cross_paper
        ),
        answerability_accuracy=_mean(
            float(sample.answer.metrics.answerability_correct) for sample in samples
        ),
        unanswerable_refusal_rate=_mean(
            float(sample.answer.answer_status == "insufficient_evidence") for sample in unanswerable
        ),
        correctness=_mean(sample.judge.decision.correctness.score / 4 for sample in samples),
        faithfulness=_mean(sample.judge.decision.faithfulness.score / 4 for sample in samples),
        citation_completeness=_mean(
            sample.judge.decision.citation_completeness.score / 4 for sample in samples
        ),
        strict_run_pass_rate=_mean(float(sample.strict_pass) for sample in samples),
        p50_workflow_latency_ms=round(
            _percentile([sample.workflow_latency_ms for sample in samples], 0.50), 2
        ),
        p95_workflow_latency_ms=round(
            _percentile([sample.workflow_latency_ms for sample in samples], 0.95), 2
        ),
        known_planner_input_tokens=sum(
            execution.planner_input_tokens or 0 for execution in executions
        ),
        known_planner_output_tokens=sum(
            execution.planner_output_tokens or 0 for execution in executions
        ),
        known_answer_input_tokens=sum(sample.answer_input_tokens or 0 for sample in samples),
        known_answer_output_tokens=sum(sample.answer_output_tokens or 0 for sample in samples),
        judge_input_tokens=sum(sample.judge_input_tokens or 0 for sample in samples),
        judge_output_tokens=sum(sample.judge_output_tokens or 0 for sample in samples),
        model_call_count=sum(sample.model_call_count for sample in samples),
        planning=_build_planning_summary(executions) if executions else None,
    )


def _build_planning_summary(
    executions: Sequence[AgentExecutionMetrics],
) -> AgentPlanningSummary:
    unnecessary = [item for item in executions if not item.revision_expected]
    expected_revision = [item for item in executions if item.revision_expected]
    return AgentPlanningSummary(
        router_accuracy=_mean(float(item.router_correct) for item in executions),
        task_count_accuracy=_mean(float(item.task_count_correct) for item in executions),
        task_coverage=_mean(item.task_coverage for item in executions),
        title_leakage_rate=_mean(float(bool(item.title_leaks)) for item in executions),
        retrieval_strategy_accuracy=_mean(
            float(item.retrieval_strategy_correct) for item in executions
        ),
        unnecessary_revision_rate=_mean(float(item.retry_count > 0) for item in unnecessary),
        revision_recovery_rate=(
            _mean(
                float(item.retry_count > 0 and item.revision_correct) for item in expected_revision
            )
            if expected_revision
            else None
        ),
        citation_validation_rate=_mean(
            float(item.citation_validation_passed) for item in executions
        ),
        p50_planning_latency_ms=round(
            _percentile([item.planning_latency_ms for item in executions], 0.50), 2
        ),
        p95_planning_latency_ms=round(
            _percentile([item.planning_latency_ms for item in executions], 0.95), 2
        ),
    )


def _markdown_report(
    report: AgentEvaluationReport,
    results: Sequence[AgentVariantCaseResult],
) -> str:
    lines = [
        f"# Agent Runtime Evaluation：{report.config.baseline_id}",
        "",
        f"- Cases：{len(report.config.case_ids)}",
        f"- Collection：`{report.config.collection_name}`",
        f"- Planner / Answer / Judge：`{report.config.planner_model}` / "
        f"`{report.config.answer_model}` / `{report.config.judge_model}`",
        "- 固定对照使用已保存样本；LangGraph Agent 使用同一 Answer/Judge 口径。",
        "",
        "## 总体对照",
        "",
        "| Variant | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 All/Cross | "
        "Answerability | Correctness | Faithfulness | Citation Completeness | Strict Run | "
        "Workflow P50/P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in report.variants:
        lines.append(
            f"| {summary.variant_id} | {summary.paper_recall_at_10:.2%} | "
            f"{summary.exact_page_recall_at_10:.2%} | "
            f"{summary.complete_papers_at_10:.2%} / "
            f"{summary.cross_paper_complete_papers_at_10:.2%} | "
            f"{summary.answerability_accuracy:.2%} | {summary.correctness:.2%} | "
            f"{summary.faithfulness:.2%} | {summary.citation_completeness:.2%} | "
            f"{summary.strict_run_pass_rate:.2%} | "
            f"{summary.p50_workflow_latency_ms:.0f} / "
            f"{summary.p95_workflow_latency_ms:.0f} ms |"
        )
    lines.extend(["", "## Agent 决策质量", ""])
    agent_variants = [item for item in report.variants if item.planning is not None]
    if agent_variants:
        lines.extend(
            [
                "| Variant | Router | Task Count | Task Coverage | Title Leakage | Strategy | "
                "Unnecessary Revision | Citation Validation | Planning P50/P95 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for summary in agent_variants:
            planning = summary.planning
            assert planning is not None
            lines.append(
                f"| {summary.variant_id} | {planning.router_accuracy:.2%} | "
                f"{planning.task_count_accuracy:.2%} | {planning.task_coverage:.2%} | "
                f"{planning.title_leakage_rate:.2%} | "
                f"{planning.retrieval_strategy_accuracy:.2%} | "
                f"{planning.unnecessary_revision_rate:.2%} | "
                f"{planning.citation_validation_rate:.2%} | "
                f"{planning.p50_planning_latency_ms:.0f} / "
                f"{planning.p95_planning_latency_ms:.0f} ms |"
            )
    lines.extend(
        [
            "",
            "## 逐题结果",
            "",
            "| Variant | Case | Route | Tasks | Retry | Papers | Answer | Judge C/F/CC | Strict |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for result in results:
        execution = result.execution
        route = execution.actual_question_type if execution else "fixed"
        tasks = str(execution.task_count) if execution else "-"
        retry = str(execution.retry_count) if execution else "-"
        papers = (
            f"{result.retrieval.paper_recall_at_10:.0%}"
            if result.retrieval.paper_recall_at_10 is not None
            else "N/A"
        )
        decision = result.judge.decision
        lines.append(
            f"| {result.variant_id} | {result.case_id} | {route} | {tasks} | {retry} | "
            f"{papers} | {result.answer.answer_status} | {decision.correctness.score}/"
            f"{decision.faithfulness.score}/{decision.citation_completeness.score} | "
            f"{result.strict_pass} |"
        )
    lines.extend(
        [
            "",
            "## 成本与解释限制",
            "",
            "| Variant | Model Calls | Known Planner Input/Output | Known Answer Input/Output | "
            "Judge Input/Output |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for summary in report.variants:
        lines.append(
            f"| {summary.variant_id} | {summary.model_call_count} | "
            f"{summary.known_planner_input_tokens} / "
            f"{summary.known_planner_output_tokens} | "
            f"{summary.known_answer_input_tokens} / "
            f"{summary.known_answer_output_tokens} | "
            f"{summary.judge_input_tokens} / {summary.judge_output_tokens} |"
        )
    lines.extend(
        [
            "",
            "- Cache 命中仍使用缓存中记录的原始生成延迟，避免把缓存查找耗时当作线上冷启动延迟。",
            "- 历史 Planner 缓存若创建于 Token tracing 之前，其 Token 记为 unknown，不做估算。",
            "- `Revision Recovery` 只有数据集中存在 `should_retry=true` 的样本时才有定义。",
            "- 单次架构对照用于发现差异；稳定性结论仍应使用多次重复实验。",
        ]
    )
    return "\n".join(lines) + "\n"


def _strict_pass(answer: AnswerCaseResult, judge: JudgeCaseResult) -> bool:
    decision = judge.decision
    return (
        answer.metrics.generation_succeeded
        and answer.metrics.answerability_correct
        and decision.correctness.score >= 3
        and decision.faithfulness.score >= 3
        and decision.citation_completeness.score >= 3
    )


def _answer_usage(answer: AnswerCaseResult) -> tuple[int | None, int | None, int]:
    if answer.generation_trace is None:
        return None, None, 1
    attempts = answer.generation_trace.attempts
    input_tokens = [item.usage.input_tokens for item in attempts]
    output_tokens = [item.usage.output_tokens for item in attempts]
    return _sum_known(input_tokens), _sum_known(output_tokens), len(attempts)


def _effective_planner_latency(event: AgentEvent) -> float:
    generation_latency = event.details.get("generation_latency_ms")
    return (
        float(generation_latency)
        if isinstance(generation_latency, int | float)
        else float(event.latency_ms)
    )


def _event_int(event: AgentEvent, key: str) -> int:
    value = event.details.get(key)
    return value if isinstance(value, int) else 0


def _sum_event_tokens(events: Sequence[AgentEvent], key: str) -> int | None:
    values = [_event_int(event, key) for event in events if key in event.details]
    return sum(values) if values else None


def _sum_known(values: Sequence[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _mean_known(values: Iterable[float | None]) -> float:
    known = [value for value in values if value is not None]
    return _mean(known)


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]
