import pytest

from paper_research_copilot.agent import (
    AgentRuntimeConfig,
    EvidenceAssessment,
    PlanningResult,
    ResearchAgentRuntime,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import Answer, Citation, PaperChunk, RetrievedChunk
from paper_research_copilot.storage import SqliteCheckpointStore

QUESTION = "How does durable memory improve later attempts?"


class _Planner:
    def __init__(self) -> None:
        self.plan_calls = 0

    def plan(self, question: str) -> PlanningResult:
        self.plan_calls += 1
        return PlanningResult(
            plan=ResearchPlan(
                question=question,
                question_type="single_paper",
                rationale="Find the mechanism",
                tasks=(
                    ResearchTask(
                        task_id="T1",
                        query="durable memory later attempts",
                        goal="Find direct evidence",
                    ),
                ),
            ),
            operation="initial",
            model="fake-planner",
            prompt_version="test",
            cache_hit=False,
            latency_ms=1,
            generation_latency_ms=1,
        )

    def revise(
        self,
        question: str,
        previous_plan: ResearchPlan,
        assessment: EvidenceAssessment,
    ) -> PlanningResult:
        raise AssertionError("Revision should not be needed")


def _candidate() -> RetrievedChunk:
    text = "Durable memory lets the system reuse successful experience."
    return RetrievedChunk(
        citation_id="C1",
        score=0.9,
        chunk=PaperChunk(
            chunk_id="chunk-1",
            document_sha256="a" * 64,
            chunk_index=1,
            chunking_version="chunking_v1",
            paper_id="paper-1",
            title="Durable Agents",
            source_path="paper-1.pdf",
            page_number=1,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


class _FailingRetriever:
    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        raise RuntimeError("simulated process interruption")


class _SuccessfulRetriever:
    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return (_candidate(),)


class _Writer:
    def generate(
        self,
        question: str,
        evidence: tuple[RetrievedChunk, ...],
    ) -> Answer:
        item = evidence[0]
        return Answer(
            question=question,
            text="Durable memory reuses prior experience [C1].",
            citations=(
                Citation(
                    citation_id="C1",
                    chunk_id=item.chunk.chunk_id,
                    paper_id=item.chunk.paper_id,
                    title=item.chunk.title,
                    source_path=item.chunk.source_path,
                    page_number=item.chunk.page_number,
                    excerpt=item.chunk.text,
                    retrieval_score=item.score,
                ),
            ),
        )


def _runtime(planner, retriever, store) -> ResearchAgentRuntime:
    return ResearchAgentRuntime(
        planner,
        retriever,
        _Writer(),
        config=AgentRuntimeConfig(
            top_k=1,
            candidate_pool_per_task=1,
            max_retries=0,
            min_chunks_per_task=1,
        ),
        checkpointer=store.saver,
    )


def test_langgraph_resumes_after_reopening_sqlite_checkpoint(tmp_path) -> None:
    path = tmp_path / "checkpoints.db"
    first_store = SqliteCheckpointStore(path)
    first_planner = _Planner()
    first_runtime = _runtime(first_planner, _FailingRetriever(), first_store)
    first_events = []

    with pytest.raises(RuntimeError, match="simulated process interruption"):
        first_runtime.run(
            QUESTION,
            task_id="task-resume",
            event_callback=first_events.append,
        )

    assert first_planner.plan_calls == 1
    assert [event.node for event in first_events] == ["plan_research"]
    assert first_store.has_checkpoint("task-resume")
    first_runtime.close()
    first_store.close()

    second_store = SqliteCheckpointStore(path)
    second_planner = _Planner()
    second_runtime = _runtime(second_planner, _SuccessfulRetriever(), second_store)
    resumed_events = []
    result = second_runtime.resume(
        "task-resume",
        event_callback=resumed_events.append,
    )

    assert second_planner.plan_calls == 0
    assert result.answer.status == "answered"
    assert result.trace[0].node == "plan_research"
    assert "plan_research" not in [event.node for event in resumed_events]
    assert [event.node for event in resumed_events] == [
        "retrieve_evidence",
        "assess_evidence",
        "write_report",
        "validate_citations",
    ]
    second_runtime.close()
    second_store.close()
