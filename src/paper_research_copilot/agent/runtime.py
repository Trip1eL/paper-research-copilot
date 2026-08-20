"""Bounded LangGraph runtime that orchestrates the existing RAG components."""

import time
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from typing import Any, Literal, Protocol, cast, runtime_checkable

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from paper_research_copilot.agent.models import (
    AgentAcquisitionSummary,
    AgentEvent,
    AgentResult,
    AgentRuntimeConfig,
    EvidenceAssessment,
    ResearchTask,
)
from paper_research_copilot.agent.planner import ResearchPlanner
from paper_research_copilot.agent.state import ResearchState
from paper_research_copilot.domain import AcquisitionResult, Answer, RetrievedChunk
from paper_research_copilot.reporting import AnswerGenerationTrace
from paper_research_copilot.retrieval import CandidateRetriever, coverage_round_robin

_EVENT_CALLBACK: ContextVar[Callable[[AgentEvent], None] | None] = ContextVar(
    "research_agent_event_callback",
    default=None,
)


class AnswerWriter(Protocol):
    def generate(
        self,
        question: str,
        evidence: Sequence[RetrievedChunk],
    ) -> Answer: ...


class EvidenceAcquirer(Protocol):
    def acquire(
        self,
        query: str,
        *,
        task_id: str | None = None,
        round_number: int = 1,
    ) -> AcquisitionResult: ...


@runtime_checkable
class ObservableAnswerWriter(AnswerWriter, Protocol):
    def trace_for(self, question: str) -> AnswerGenerationTrace: ...


class ResearchAgentRuntime:
    """Execute one research plan with at most one evidence-driven query revision."""

    def __init__(
        self,
        planner: ResearchPlanner,
        retriever: CandidateRetriever,
        answer_writer: AnswerWriter,
        *,
        acquirer: EvidenceAcquirer | None = None,
        config: AgentRuntimeConfig | None = None,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        close_callback: Callable[[], None] | None = None,
    ) -> None:
        self._planner = planner
        self._retriever = retriever
        self._answer_writer = answer_writer
        self._acquirer = acquirer
        self.config = config or AgentRuntimeConfig()
        self._checkpointer = checkpointer
        self._close_callback = close_callback
        self._closed = False
        self._graph = self._build_graph()

    def run(
        self,
        question: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
        task_id: str | None = None,
    ) -> AgentResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Research question must not be empty")
        if self._closed:
            raise RuntimeError("Research Agent Runtime is closed")
        initial = ResearchState(
            question=normalized_question,
            task_id=task_id,
            retry_count=0,
            acquisition_rounds=0,
            acquisition=None,
            trace=(),
            evidence=(),
            rankings_by_task={},
            task_candidate_counts={},
            task_selected_counts={},
        )
        config = self._graph_config(task_id)
        token = _EVENT_CALLBACK.set(event_callback)
        try:
            final_state = self._graph.invoke(initial, config=config)
        finally:
            _EVENT_CALLBACK.reset(token)
        return self._result(normalized_question, cast(ResearchState, final_state))

    def can_resume(self, task_id: str) -> bool:
        if self._checkpointer is None:
            return False
        return self._checkpointer.get_tuple(self._graph_config(task_id)) is not None

    def resume(
        self,
        task_id: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
    ) -> AgentResult:
        if self._closed:
            raise RuntimeError("Research Agent Runtime is closed")
        if not self.can_resume(task_id):
            raise LookupError(f"No LangGraph checkpoint exists for task: {task_id}")
        token = _EVENT_CALLBACK.set(event_callback)
        try:
            final_state = self._graph.invoke(None, config=self._graph_config(task_id))
        finally:
            _EVENT_CALLBACK.reset(token)
        typed_state = cast(ResearchState, final_state)
        question = typed_state["question"]
        return self._result(question, typed_state)

    def _result(self, question: str, final_state: ResearchState) -> AgentResult:
        return AgentResult(
            question=question,
            plan=final_state["plan"],
            evidence=final_state["evidence"],
            assessment=final_state["assessment"],
            answer=final_state["answer"],
            retry_count=final_state["retry_count"],
            acquisition_rounds=final_state.get("acquisition_rounds", 0),
            acquisition=final_state.get("acquisition"),
            trace=final_state["trace"],
        )

    def close(self) -> None:
        if not self._closed and self._close_callback is not None:
            self._close_callback()
        self._closed = True

    def _build_graph(
        self,
    ) -> CompiledStateGraph[ResearchState, None, ResearchState, ResearchState]:
        graph = StateGraph(ResearchState)
        graph.add_node("plan_research", self._plan_research)
        graph.add_node("retrieve_evidence", self._retrieve_evidence)
        graph.add_node("assess_evidence", self._assess_evidence)
        graph.add_node("revise_queries", self._revise_queries)
        graph.add_node("acquire_evidence", self._acquire_evidence)
        graph.add_node("write_report", self._write_report)
        graph.add_node("validate_citations", self._validate_citations)
        graph.add_edge(START, "plan_research")
        graph.add_edge("plan_research", "retrieve_evidence")
        graph.add_edge("retrieve_evidence", "assess_evidence")
        graph.add_conditional_edges(
            "assess_evidence",
            self._route_after_assessment,
            {
                "revise": "revise_queries",
                "acquire": "acquire_evidence",
                "write": "write_report",
            },
        )
        graph.add_edge("revise_queries", "retrieve_evidence")
        graph.add_edge("acquire_evidence", "retrieve_evidence")
        graph.add_conditional_edges(
            "write_report",
            self._route_after_writing,
            {
                "revise": "revise_queries",
                "acquire": "acquire_evidence",
                "validate": "validate_citations",
            },
        )
        graph.add_edge("validate_citations", END)
        return graph.compile(
            checkpointer=self._checkpointer,
            name="paper-research-agent-v2",
        )

    def _graph_config(self, task_id: str | None) -> RunnableConfig:
        config: RunnableConfig = {"recursion_limit": 16}
        if self._checkpointer is not None:
            if not task_id:
                raise ValueError("task_id is required when checkpointing is enabled")
            config["configurable"] = {"thread_id": task_id}
        return config

    def _plan_research(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        result = self._planner.plan(state["question"])
        latency_ms = _elapsed_ms(started)
        return ResearchState(
            plan=result.plan,
            trace=_append_event(
                state,
                node="plan_research",
                outcome="planned",
                latency_ms=latency_ms,
                details={
                    "question_type": result.plan.question_type,
                    "task_count": len(result.plan.tasks),
                    "planner_model": result.model,
                    "cache_hit": result.cache_hit,
                    "generation_latency_ms": result.generation_latency_ms,
                    "planner_attempts": result.attempts,
                    **_token_usage_details("planner", result.usage),
                },
            ),
        )

    def _retrieve_evidence(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        plan = state["plan"]
        rankings = {
            task.task_id: self._retriever.retrieve(
                task.query,
                self.config.candidate_pool_per_task,
            )
            for task in plan.tasks
        }
        if plan.question_type == "single_paper":
            first_ranking = rankings[plan.tasks[0].task_id]
            evidence = _renumber_citations(first_ranking[: self.config.top_k])
            selected_counts = {plan.tasks[0].task_id: len(evidence)}
            strategy = "federated_hybrid_rrf"
        else:
            ordered_rankings = tuple(rankings[task.task_id] for task in plan.tasks)
            evidence, counts = coverage_round_robin(
                ordered_rankings,
                top_k=self.config.top_k,
            )
            selected_counts = {
                task.task_id: count for task, count in zip(plan.tasks, counts, strict=True)
            }
            strategy = "coverage_federated_hybrid_rrf"
        candidate_counts = {task_id: len(candidates) for task_id, candidates in rankings.items()}
        latency_ms = _elapsed_ms(started)
        return ResearchState(
            rankings_by_task=rankings,
            evidence=evidence,
            task_candidate_counts=candidate_counts,
            task_selected_counts=selected_counts,
            trace=_append_event(
                state,
                node="retrieve_evidence",
                outcome="retrieved",
                latency_ms=latency_ms,
                details={
                    "strategy": strategy,
                    "candidate_counts": _format_counts(candidate_counts),
                    "selected_counts": _format_counts(selected_counts),
                    "evidence_count": len(evidence),
                    "dynamic_evidence_count": sum(
                        item.chunk.corpus_id == "paper-dynamic" for item in evidence
                    ),
                },
            ),
        )

    def _assess_evidence(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        plan = state["plan"]
        selected_counts = state["task_selected_counts"]
        required_per_task = min(
            self.config.min_chunks_per_task,
            max(1, self.config.top_k // len(plan.tasks)),
        )
        missing_task_ids = tuple(
            task.task_id
            for task in plan.tasks
            if selected_counts.get(task.task_id, 0) < required_per_task
        )
        paper_ids = {item.chunk.paper_id or item.chunk.source_path for item in state["evidence"]}
        paper_coverage_ok = plan.question_type == "single_paper" or len(paper_ids) >= 2
        sufficient = bool(state["evidence"]) and not missing_task_ids and paper_coverage_ok
        if not state["evidence"]:
            reason = "No evidence was retrieved"
        elif missing_task_ids:
            reason = f"Tasks below evidence quota: {', '.join(missing_task_ids)}"
        elif not paper_coverage_ok:
            reason = "Cross-paper plan retrieved fewer than two distinct papers"
        else:
            reason = "Every task met its evidence quota and paper coverage requirement"
        retry_recommended = not sufficient and state["retry_count"] < self.config.max_retries
        assessment = EvidenceAssessment(
            sufficient=sufficient,
            reason=reason,
            task_candidate_counts=state["task_candidate_counts"],
            task_selected_counts=selected_counts,
            missing_task_ids=missing_task_ids,
            distinct_paper_count=len(paper_ids),
            retry_recommended=retry_recommended,
        )
        return ResearchState(
            assessment=assessment,
            trace=_append_event(
                state,
                node="assess_evidence",
                outcome="sufficient" if sufficient else "insufficient",
                latency_ms=_elapsed_ms(started),
                details={
                    "reason": reason,
                    "distinct_papers": len(paper_ids),
                    "retry_recommended": retry_recommended,
                },
            ),
        )

    def _route_after_assessment(
        self,
        state: ResearchState,
    ) -> Literal["revise", "acquire", "write"]:
        if state["assessment"].retry_recommended:
            return "revise"
        if (
            not state["assessment"].sufficient
            and self._acquirer is not None
            and state.get("acquisition_rounds", 0)
            < self.config.max_acquisition_rounds
        ):
            return "acquire"
        return "write"

    def _revise_queries(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        result = self._planner.revise(
            state["question"],
            state["plan"],
            state["assessment"],
        )
        retry_count = state["retry_count"] + 1
        return ResearchState(
            plan=result.plan,
            retry_count=retry_count,
            trace=_append_event(
                state,
                node="revise_queries",
                outcome="revised",
                latency_ms=_elapsed_ms(started),
                details={
                    "retry_count": retry_count,
                    "planner_model": result.model,
                    "cache_hit": result.cache_hit,
                    "generation_latency_ms": result.generation_latency_ms,
                    "planner_attempts": result.attempts,
                    **_token_usage_details("planner", result.usage),
                },
            ),
        )

    def _route_after_writing(
        self,
        state: ResearchState,
    ) -> Literal["revise", "acquire", "validate"]:
        if state["answer"].status != "insufficient_evidence":
            return "validate"
        if state["assessment"].retry_recommended:
            return "revise"
        if (
            self._acquirer is not None
            and state.get("acquisition_rounds", 0)
            < self.config.max_acquisition_rounds
        ):
            return "acquire"
        return "validate"

    def _acquire_evidence(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        query = _select_acquisition_query(state)
        round_number = state.get("acquisition_rounds", 0) + 1
        if self._acquirer is None:
            raise RuntimeError("Acquisition node requires an Evidence Acquirer")
        try:
            result = self._acquirer.acquire(
                query,
                task_id=state.get("task_id"),
                round_number=round_number,
            )
            run = result.run
            summary = AgentAcquisitionSummary(
                query=query,
                acquisition_id=run.acquisition_id,
                status=run.status,
                candidate_count=run.candidate_count,
                selected_count=run.selected_count,
                downloaded_count=run.downloaded_count,
                indexed_count=run.indexed_count,
                asset_ids=tuple(item.asset.asset_id for item in result.ingestions),
                paper_titles=tuple(
                    item.asset.candidate.title for item in result.ingestions
                ),
                error=run.error,
            )
        except Exception as exc:
            summary = AgentAcquisitionSummary(
                query=query,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        details: dict[str, str | int | float | bool] = {
            "query": query,
            "round": round_number,
            "status": summary.status,
            "candidates": summary.candidate_count,
            "selected": summary.selected_count,
            "downloaded": summary.downloaded_count,
            "indexed": summary.indexed_count,
        }
        if summary.acquisition_id is not None:
            details["acquisition_id"] = summary.acquisition_id
        if summary.error is not None:
            details["error"] = summary.error
        return ResearchState(
            acquisition_rounds=round_number,
            acquisition=summary,
            trace=_append_event(
                state,
                node="acquire_evidence",
                outcome=summary.status,
                latency_ms=_elapsed_ms(started),
                details=details,
            ),
        )

    def _write_report(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        assessment = state["assessment"]
        if state["assessment"].sufficient:
            answer = self._answer_writer.generate(state["question"], state["evidence"])
            outcome = answer.status
            source = "answer_model"
            generation_details = _answer_generation_details(self._answer_writer, state["question"])
            if answer.status == "insufficient_evidence":
                assessment = state["assessment"].model_copy(
                    update={
                        "sufficient": False,
                        "reason": "Answer model found the supplied evidence insufficient",
                        "retry_recommended": (
                            state["retry_count"] < self.config.max_retries
                        ),
                    }
                )
        else:
            answer = Answer(
                question=state["question"],
                text="INSUFFICIENT_EVIDENCE",
                citations=(),
                status="insufficient_evidence",
            )
            outcome = "insufficient_evidence"
            source = "evidence_gate"
            generation_details = {}
        return ResearchState(
            answer=answer,
            assessment=assessment,
            trace=_append_event(
                state,
                node="write_report",
                outcome=outcome,
                latency_ms=_elapsed_ms(started),
                details={
                    "source": source,
                    "citation_count": len(answer.citations),
                    **generation_details,
                },
            ),
        )

    def _validate_citations(self, state: ResearchState) -> ResearchState:
        started = time.perf_counter()
        answer = state["answer"]
        evidence_by_id = {item.citation_id: item for item in state["evidence"]}
        if answer.status == "insufficient_evidence":
            if answer.citations:
                raise ValueError("Insufficient-evidence answer must not contain citations")
        else:
            if not answer.citations:
                raise ValueError("Answered Agent result must contain at least one citation")
            for citation in answer.citations:
                evidence = evidence_by_id.get(citation.citation_id)
                if evidence is None or evidence.chunk.chunk_id != citation.chunk_id:
                    raise ValueError(
                        f"Agent citation does not map to final Evidence: {citation.citation_id}"
                    )
        return ResearchState(
            trace=_append_event(
                state,
                node="validate_citations",
                outcome="valid",
                latency_ms=_elapsed_ms(started),
                details={
                    "answer_status": answer.status,
                    "citation_count": len(answer.citations),
                },
            )
        )


def _renumber_citations(
    evidence: Sequence[RetrievedChunk],
) -> tuple[RetrievedChunk, ...]:
    return tuple(
        item.model_copy(update={"citation_id": f"C{index}"})
        for index, item in enumerate(evidence, start=1)
    )


def _select_acquisition_query(state: ResearchState) -> str:
    missing = set(state["assessment"].missing_task_ids)
    tasks = tuple(
        task for task in state["plan"].tasks if not missing or task.task_id in missing
    )
    if not tasks:
        tasks = state["plan"].tasks

    def weakness(task: ResearchTask) -> tuple[int, int, int, str]:
        ranking = state["rankings_by_task"].get(task.task_id, ())
        distinct_papers = len(
            {item.chunk.paper_id or item.chunk.source_path for item in ranking}
        )
        return (
            distinct_papers,
            state["task_selected_counts"].get(task.task_id, 0),
            state["task_candidate_counts"].get(task.task_id, 0),
            task.task_id,
        )

    return min(tasks, key=weakness).query


def _append_event(
    state: ResearchState,
    *,
    node: str,
    outcome: str,
    latency_ms: float,
    details: dict[str, str | int | float | bool],
) -> tuple[AgentEvent, ...]:
    trace = state.get("trace", ())
    event = AgentEvent(
        sequence=len(trace) + 1,
        node=node,
        outcome=outcome,
        latency_ms=latency_ms,
        details=details,
    )
    callback = _EVENT_CALLBACK.get()
    if callback is not None:
        callback(event)
    return (*trace, event)


def _format_counts(counts: dict[str, int]) -> str:
    return ",".join(f"{task_id}={count}" for task_id, count in counts.items())


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _token_usage_details(prefix: str, usage: object) -> dict[str, int]:
    details: dict[str, int] = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        value = getattr(usage, field, None)
        if isinstance(value, int):
            details[f"{prefix}_{field}"] = value
    return details


def _answer_generation_details(writer: AnswerWriter, question: str) -> dict[str, str | int]:
    if not isinstance(writer, ObservableAnswerWriter):
        return {}
    try:
        trace = writer.trace_for(question)
    except LookupError:
        return {}
    input_tokens = sum(
        attempt.usage.input_tokens or 0
        for attempt in trace.attempts
        if attempt.usage.input_tokens is not None
    )
    output_tokens = sum(
        attempt.usage.output_tokens or 0
        for attempt in trace.attempts
        if attempt.usage.output_tokens is not None
    )
    details: dict[str, str | int] = {
        "answer_attempts": len(trace.attempts),
        "answer_final_outcome": trace.final_outcome,
    }
    if input_tokens:
        details["answer_input_tokens"] = input_tokens
    if output_tokens:
        details["answer_output_tokens"] = output_tokens
    return details
