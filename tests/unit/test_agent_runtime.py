from paper_research_copilot.agent import (
    AgentRuntimeConfig,
    EvidenceAssessment,
    PlanningResult,
    ResearchAgentRuntime,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import Answer, Citation, PaperChunk, RetrievedChunk


def _task(task_id: str, query: str) -> ResearchTask:
    return ResearchTask(task_id=task_id, query=query, goal=f"Find evidence for {task_id}")


def _plan(
    question: str,
    *tasks: ResearchTask,
    revision: int = 0,
) -> ResearchPlan:
    return ResearchPlan(
        question=question,
        question_type="single_paper" if len(tasks) == 1 else "cross_paper",
        rationale="Retrieve each requested mechanism independently",
        tasks=tasks,
        revision=revision,
    )


def _planning_result(plan: ResearchPlan, operation: str = "initial") -> PlanningResult:
    return PlanningResult(
        plan=plan,
        operation=operation,  # type: ignore[arg-type]
        model="fake-planner",
        prompt_version="research_planner_v1",
        cache_hit=False,
        latency_ms=1,
        generation_latency_ms=1,
    )


def _candidate(number: int, paper_id: str) -> RetrievedChunk:
    text = f"Evidence {number} from {paper_id}."
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=1 / number,
        chunk=PaperChunk(
            chunk_id=f"chunk-{number}-{paper_id}",
            document_sha256="a" * 64,
            chunk_index=number,
            chunking_version="chunking_v1",
            paper_id=paper_id,
            title=f"Paper {paper_id}",
            source_path=f"{paper_id}.pdf",
            page_number=number,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


class _FakePlanner:
    def __init__(self, initial: ResearchPlan, revised: ResearchPlan | None = None) -> None:
        self.initial = initial
        self.revised = revised
        self.plan_calls = 0
        self.revise_calls = 0

    def plan(self, question: str) -> PlanningResult:
        self.plan_calls += 1
        assert question == self.initial.question
        return _planning_result(self.initial)

    def revise(
        self,
        question: str,
        previous_plan: ResearchPlan,
        assessment: EvidenceAssessment,
    ) -> PlanningResult:
        self.revise_calls += 1
        assert not assessment.sufficient
        assert previous_plan == self.initial
        assert self.revised is not None
        return _planning_result(self.revised, "revision")


class _FakeRetriever:
    def __init__(self, rankings: dict[str, tuple[RetrievedChunk, ...]]) -> None:
        self.rankings = rankings
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.calls.append((question, top_k))
        return self.rankings.get(question, ())[:top_k]


class _GroundedWriter:
    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self,
        question: str,
        evidence: tuple[RetrievedChunk, ...],
    ) -> Answer:
        self.calls += 1
        first = evidence[0]
        chunk = first.chunk
        return Answer(
            question=question,
            text="Grounded answer [C1].",
            citations=(
                Citation(
                    citation_id=first.citation_id,
                    chunk_id=chunk.chunk_id,
                    paper_id=chunk.paper_id,
                    title=chunk.title,
                    source_path=chunk.source_path,
                    page_number=chunk.page_number,
                    excerpt=chunk.text,
                    retrieval_score=first.score,
                ),
            ),
        )


def _config(*, max_retries: int = 1) -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        top_k=4,
        candidate_pool_per_task=4,
        max_retries=max_retries,
        min_chunks_per_task=1,
    )


def test_single_paper_plan_uses_one_retrieval_without_revision() -> None:
    question = "How does episodic memory improve later attempts?"
    plan = _plan(question, _task("T1", "episodic memory later attempts"))
    planner = _FakePlanner(plan)
    retriever = _FakeRetriever({"episodic memory later attempts": (_candidate(1, "paper-a"),)})
    writer = _GroundedWriter()
    runtime = ResearchAgentRuntime(planner, retriever, writer, config=_config())

    result = runtime.run(question)

    assert result.plan.question_type == "single_paper"
    assert result.retry_count == 0
    assert planner.revise_calls == 0
    assert retriever.calls == [("episodic memory later attempts", 4)]
    assert [event.node for event in result.trace] == [
        "plan_research",
        "retrieve_evidence",
        "assess_evidence",
        "write_report",
        "validate_citations",
    ]


def test_runtime_emits_each_agent_event_to_callback_in_order() -> None:
    question = "How does episodic memory improve later attempts?"
    plan = _plan(question, _task("T1", "episodic memory later attempts"))
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        _FakeRetriever({"episodic memory later attempts": (_candidate(1, "paper-a"),)}),
        _GroundedWriter(),
        config=_config(),
    )
    observed = []

    result = runtime.run(question, event_callback=observed.append)

    assert tuple(observed) == result.trace


def test_cross_paper_plan_preserves_both_task_quotas() -> None:
    question = "How do two described mechanisms differ?"
    plan = _plan(
        question,
        _task("T1", "first described mechanism"),
        _task("T2", "second described mechanism"),
    )
    retriever = _FakeRetriever(
        {
            "first described mechanism": (
                _candidate(1, "paper-a"),
                _candidate(2, "paper-a"),
            ),
            "second described mechanism": (
                _candidate(3, "paper-b"),
                _candidate(4, "paper-b"),
            ),
        }
    )
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        retriever,
        _GroundedWriter(),
        config=_config(),
    )

    result = runtime.run(question)

    assert result.assessment.sufficient
    assert result.assessment.task_selected_counts == {"T1": 2, "T2": 2}
    assert [item.chunk.paper_id for item in result.evidence] == [
        "paper-a",
        "paper-b",
        "paper-a",
        "paper-b",
    ]


def test_insufficient_cross_paper_evidence_revises_once_then_succeeds() -> None:
    question = "How do two described mechanisms differ?"
    initial = _plan(
        question,
        _task("T1", "first weak query"),
        _task("T2", "second weak query"),
    )
    revised = _plan(
        question,
        _task("T1", "first improved query"),
        _task("T2", "second improved query"),
        revision=1,
    )
    planner = _FakePlanner(initial, revised)
    retriever = _FakeRetriever(
        {
            "first weak query": (_candidate(1, "paper-a"),),
            "second weak query": (_candidate(2, "paper-a"),),
            "first improved query": (_candidate(3, "paper-a"),),
            "second improved query": (_candidate(4, "paper-b"),),
        }
    )
    runtime = ResearchAgentRuntime(
        planner,
        retriever,
        _GroundedWriter(),
        config=_config(),
    )

    result = runtime.run(question)

    assert result.retry_count == 1
    assert result.assessment.sufficient
    assert planner.revise_calls == 1
    assert [event.node for event in result.trace].count("assess_evidence") == 2
    assert [event.node for event in result.trace].count("retrieve_evidence") == 2


def test_retry_exhaustion_returns_deterministic_insufficient_evidence() -> None:
    question = "How do two described mechanisms differ?"
    initial = _plan(
        question,
        _task("T1", "first weak query"),
        _task("T2", "second weak query"),
    )
    revised = _plan(
        question,
        _task("T1", "first revised query"),
        _task("T2", "second revised query"),
        revision=1,
    )
    writer = _GroundedWriter()
    runtime = ResearchAgentRuntime(
        _FakePlanner(initial, revised),
        _FakeRetriever(
            {
                query: (_candidate(index, "paper-a"),)
                for index, query in enumerate(
                    (
                        "first weak query",
                        "second weak query",
                        "first revised query",
                        "second revised query",
                    ),
                    start=1,
                )
            }
        ),
        writer,
        config=_config(),
    )

    result = runtime.run(question)

    assert not result.assessment.sufficient
    assert result.retry_count == 1
    assert result.answer.status == "insufficient_evidence"
    assert result.answer.text == "INSUFFICIENT_EVIDENCE"
    assert writer.calls == 0
    write_event = next(event for event in result.trace if event.node == "write_report")
    assert write_event.details["source"] == "evidence_gate"


def test_close_callback_is_idempotent() -> None:
    closed = 0

    def close() -> None:
        nonlocal closed
        closed += 1

    question = "How does episodic memory improve later attempts?"
    plan = _plan(question, _task("T1", "episodic memory later attempts"))
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        _FakeRetriever({}),
        _GroundedWriter(),
        config=_config(max_retries=0),
        close_callback=close,
    )

    runtime.close()
    runtime.close()

    assert closed == 1
