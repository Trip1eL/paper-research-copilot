from datetime import UTC, datetime

from paper_research_copilot.agent import (
    AgentRuntimeConfig,
    ClaimAssessment,
    ClaimVerification,
    ClaimVerificationOutcome,
    EvidenceAssessment,
    PlanningResult,
    QuestionAmbiguityGate,
    ResearchAgentRuntime,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import (
    AcquisitionBudget,
    AcquisitionResult,
    AcquisitionRun,
    Answer,
    Citation,
    PaperChunk,
    RetrievedChunk,
)


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
    def __init__(
        self,
        initial: ResearchPlan,
        revised: ResearchPlan | None = None,
        *,
        revision_fallback: bool = False,
    ) -> None:
        self.initial = initial
        self.revised = revised
        self.revision_fallback = revision_fallback
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
        result = _planning_result(self.revised, "revision")
        if self.revision_fallback:
            return result.model_copy(
                update={
                    "repair_attempts": 1,
                    "fallback_used": True,
                    "fallback_reason": "schema retries exhausted",
                }
            )
        return result


class _FakeRetriever:
    def __init__(self, rankings: dict[str, tuple[RetrievedChunk, ...]]) -> None:
        self.rankings = rankings
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.calls.append((question, top_k))
        return self.rankings.get(question, ())[:top_k]


class _AcquisitionAwareRetriever(_FakeRetriever):
    def __init__(
        self,
        before: dict[str, tuple[RetrievedChunk, ...]],
        after: dict[str, tuple[RetrievedChunk, ...]],
    ) -> None:
        super().__init__(before)
        self.after = after
        self.acquired = False

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if self.acquired:
            self.rankings = self.after
        return super().retrieve(question, top_k)


class _FakeAcquirer:
    def __init__(
        self,
        retriever: _AcquisitionAwareRetriever,
        *,
        status: str = "succeeded",
    ) -> None:
        self.retriever = retriever
        self.status = status
        self.calls: list[tuple[str, str | None, int]] = []

    def acquire(
        self,
        query: str,
        *,
        task_id: str | None = None,
        round_number: int = 1,
    ) -> AcquisitionResult:
        self.calls.append((query, task_id, round_number))
        self.retriever.acquired = self.status == "succeeded"
        now = datetime.now(UTC)
        run = AcquisitionRun(
            acquisition_id="acquisition-1",
            task_id=task_id,
            query=query,
            status=self.status,  # type: ignore[arg-type]
            budget=AcquisitionBudget(),
            candidate_count=1,
            selected_count=1,
            downloaded_count=1 if self.status == "succeeded" else 0,
            indexed_count=1 if self.status == "succeeded" else 0,
            started_at=now,
            completed_at=now,
            error=None if self.status == "succeeded" else "search failed",
        )
        return AcquisitionResult(run=run, candidates=(), ingestions=())


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


class _RefuseThenGroundedWriter(_GroundedWriter):
    def __init__(self, *, always_refuse: bool = False) -> None:
        super().__init__()
        self.always_refuse = always_refuse

    def generate(
        self,
        question: str,
        evidence: tuple[RetrievedChunk, ...],
    ) -> Answer:
        self.calls += 1
        if self.always_refuse or self.calls == 1:
            return Answer(
                question=question,
                text="INSUFFICIENT_EVIDENCE",
                citations=(),
                status="insufficient_evidence",
            )
        self.calls -= 1
        return super().generate(question, evidence)


class _FakeClaimVerifier:
    model = "fake-verifier"

    def __init__(self, *, revised_text: str | None = None, error: Exception | None = None) -> None:
        self.revised_text = revised_text
        self.error = error
        self.calls = 0

    def verify(
        self,
        question: str,
        answer: Answer,
        evidence: tuple[RetrievedChunk, ...],
    ) -> ClaimVerificationOutcome:
        self.calls += 1
        if self.error is not None:
            raise self.error
        revised = self.revised_text is not None
        final_answer = (
            answer.model_copy(update={"text": self.revised_text}) if revised else answer
        )
        return ClaimVerificationOutcome(
            answer=final_answer,
            verification=ClaimVerification(
                status="revised" if revised else "passed",
                claims=(
                    ClaimAssessment(
                        claim_id="CL1",
                        claim="The answer states a grounded mechanism",
                        citation_ids=("C1",),
                        verdict="unsupported" if revised else "supported",
                        rationale="Compared directly with the cited Evidence",
                    ),
                ),
                rationale="The answer was checked against cited Evidence",
                model=self.model,
                attempts=1,
            ),
        )


def _config(
    *,
    max_retries: int = 1,
    max_acquisition_rounds: int = 0,
) -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        top_k=4,
        candidate_pool_per_task=4,
        max_retries=max_retries,
        max_acquisition_rounds=max_acquisition_rounds,
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


def test_claim_verification_revises_once_before_final_citation_validation() -> None:
    question = "How does episodic memory improve later attempts?"
    plan = _plan(question, _task("T1", "episodic memory later attempts"))
    verifier = _FakeClaimVerifier(revised_text="Revised grounded answer [C1].")
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        _FakeRetriever(
            {"episodic memory later attempts": (_candidate(1, "paper-a"),)}
        ),
        _GroundedWriter(),
        claim_verifier=verifier,
        config=_config(),
    )

    result = runtime.run(question)

    assert result.answer.text == "Revised grounded answer [C1]."
    assert result.verification is not None
    assert result.verification.status == "revised"
    assert verifier.calls == 1
    assert [event.node for event in result.trace][-2:] == [
        "verify_claims",
        "validate_citations",
    ]


def test_claim_verification_error_is_visible_without_failing_task() -> None:
    question = "How does episodic memory improve later attempts?"
    plan = _plan(question, _task("T1", "episodic memory later attempts"))
    verifier = _FakeClaimVerifier(error=TimeoutError("verification timeout"))
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        _FakeRetriever(
            {"episodic memory later attempts": (_candidate(1, "paper-a"),)}
        ),
        _GroundedWriter(),
        claim_verifier=verifier,
        config=_config(),
    )

    result = runtime.run(question)

    assert result.answer.status == "answered"
    assert result.verification is not None
    assert result.verification.status == "error"
    assert result.verification.needs_human_review
    assert "verification timeout" in (result.verification.error or "")
    assert result.trace[-2].node == "verify_claims"
    assert result.trace[-2].outcome == "error"


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


def test_revision_trace_exposes_repair_fallback_and_query_change() -> None:
    question = "How do two described mechanisms differ?"
    initial = _plan(
        question,
        _task("T1", "first weak query"),
        _task("T2", "second weak query"),
    )
    revised = _plan(
        question,
        _task("T1", "first fallback query"),
        _task("T2", "second fallback query"),
        revision=1,
    )
    runtime = ResearchAgentRuntime(
        _FakePlanner(initial, revised, revision_fallback=True),
        _FakeRetriever(
            {
                "first weak query": (_candidate(1, "paper-a"),),
                "second weak query": (_candidate(2, "paper-a"),),
                "first fallback query": (_candidate(3, "paper-a"),),
                "second fallback query": (_candidate(4, "paper-b"),),
            }
        ),
        _GroundedWriter(),
        config=_config(),
    )

    result = runtime.run(question)

    event = next(item for item in result.trace if item.node == "revise_queries")
    assert event.details["planner_repair_attempts"] == 1
    assert event.details["planner_fallback_used"] is True
    assert event.details["planner_fallback_reason"] == "schema retries exhausted"
    assert event.details["previous_queries"] == (
        "T1=first weak query | T2=second weak query"
    )
    assert event.details["revised_queries"] == (
        "T1=first fallback query | T2=second fallback query"
    )


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


def test_insufficient_evidence_acquires_once_after_local_revision() -> None:
    question = "How do two newly described mechanisms differ?"
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
    before = {
        "first weak query": (_candidate(1, "paper-a"),),
        "second weak query": (_candidate(2, "paper-a"),),
        "first revised query": (_candidate(3, "paper-a"),),
        "second revised query": (_candidate(4, "paper-a"),),
    }
    after = {
        **before,
        "second revised query": (_candidate(5, "paper-b"),),
    }
    retriever = _AcquisitionAwareRetriever(before, after)
    acquirer = _FakeAcquirer(retriever)
    runtime = ResearchAgentRuntime(
        _FakePlanner(initial, revised),
        retriever,
        _GroundedWriter(),
        acquirer=acquirer,
        config=_config(max_acquisition_rounds=1),
    )

    result = runtime.run(question, task_id="task-open-world")

    assert result.assessment.sufficient
    assert result.acquisition_rounds == 1
    assert result.acquisition is not None
    assert result.acquisition.status == "succeeded"
    assert acquirer.calls == [("first revised query", "task-open-world", 1)]
    assert [event.node for event in result.trace].count("acquire_evidence") == 1
    assert [event.node for event in result.trace].count("retrieve_evidence") == 3


def test_failed_acquisition_still_stops_after_one_round() -> None:
    question = "How do two unavailable mechanisms differ?"
    plan = _plan(
        question,
        _task("T1", "first unavailable mechanism"),
        _task("T2", "second unavailable mechanism"),
    )
    rankings = {
        "first unavailable mechanism": (_candidate(1, "paper-a"),),
        "second unavailable mechanism": (_candidate(2, "paper-a"),),
    }
    retriever = _AcquisitionAwareRetriever(rankings, rankings)
    acquirer = _FakeAcquirer(retriever, status="failed")
    writer = _GroundedWriter()
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        retriever,
        writer,
        acquirer=acquirer,
        config=_config(max_retries=0, max_acquisition_rounds=1),
    )

    result = runtime.run(question, task_id="task-failed-acquisition")

    assert result.answer.status == "insufficient_evidence"
    assert result.acquisition_rounds == 1
    assert result.acquisition is not None
    assert result.acquisition.status == "failed"
    assert len(acquirer.calls) == 1
    assert writer.calls == 0


def test_ambiguous_question_skips_retrieval_and_acquisition() -> None:
    question = "请详细解释刚才提到的那篇论文。"
    plan = _plan(question, _task("T1", "referenced paper details"))
    retriever = _AcquisitionAwareRetriever({}, {})
    acquirer = _FakeAcquirer(retriever)
    writer = _GroundedWriter()
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        retriever,
        writer,
        acquirer=acquirer,
        question_gate=QuestionAmbiguityGate(),
        config=_config(max_retries=0, max_acquisition_rounds=1),
    )

    result = runtime.run(question, task_id="task-ambiguous")

    assert result.screening is not None
    assert result.screening.decision == "ambiguous"
    assert result.screening.rule_id == "unresolved_reference"
    assert result.clarification is not None
    assert result.clarification.rule_id == "unresolved_reference"
    assert result.clarification.prompt == "你指的是哪一篇论文或哪一个方法？"
    assert result.answer.status == "insufficient_evidence"
    assert result.answer.text == "INSUFFICIENT_EVIDENCE"
    assert result.acquisition_rounds == 0
    assert retriever.calls == []
    assert acquirer.calls == []
    assert writer.calls == 0
    assert [event.node for event in result.trace] == [
        "plan_research",
        "screen_question",
        "write_report",
        "validate_citations",
    ]


def test_answer_model_rejection_routes_to_local_query_revision() -> None:
    question = "How does an unavailable method improve retrieval?"
    initial = _plan(question, _task("T1", "unavailable method retrieval"))
    revised = _plan(
        question,
        _task("T1", "improved unavailable method query"),
        revision=1,
    )
    retriever = _FakeRetriever(
        {
            "unavailable method retrieval": (_candidate(1, "paper-a"),),
            "improved unavailable method query": (_candidate(2, "paper-b"),),
        }
    )
    writer = _RefuseThenGroundedWriter()
    runtime = ResearchAgentRuntime(
        _FakePlanner(initial, revised),
        retriever,
        writer,
        config=_config(max_retries=1),
    )

    result = runtime.run(question)

    assert result.answer.status == "answered"
    assert result.assessment.sufficient
    assert result.retry_count == 1
    assert writer.calls == 2
    assert [event.node for event in result.trace].count("write_report") == 2
    first_write = next(event for event in result.trace if event.node == "write_report")
    assert first_write.outcome == "insufficient_evidence"
    assert first_write.details["source"] == "answer_model"


def test_answer_model_rejection_acquires_once_when_revision_is_disabled() -> None:
    question = "How does a newly published method improve retrieval?"
    plan = _plan(question, _task("T1", "NewMethod agent memory retrieval details"))
    rankings = {
        "NewMethod agent memory retrieval details": (_candidate(1, "paper-a"),),
    }
    retriever = _AcquisitionAwareRetriever(rankings, rankings)
    acquirer = _FakeAcquirer(retriever)
    writer = _RefuseThenGroundedWriter()
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        retriever,
        writer,
        acquirer=acquirer,
        config=_config(max_retries=0, max_acquisition_rounds=1),
    )

    result = runtime.run(question, task_id="task-semantic-acquisition")

    assert result.answer.status == "answered"
    assert result.assessment.sufficient
    assert result.acquisition_rounds == 1
    assert len(acquirer.calls) == 1
    assert [event.node for event in result.trace].count("acquire_evidence") == 1
    assert [event.node for event in result.trace].count("retrieve_evidence") == 2


def test_answer_model_rejection_stops_after_failed_acquisition() -> None:
    question = "How does a missing method improve retrieval?"
    plan = _plan(question, _task("T1", "MissingMethod retrieval details"))
    rankings = {"MissingMethod retrieval details": (_candidate(1, "paper-a"),)}
    retriever = _AcquisitionAwareRetriever(rankings, rankings)
    acquirer = _FakeAcquirer(retriever, status="failed")
    writer = _RefuseThenGroundedWriter(always_refuse=True)
    runtime = ResearchAgentRuntime(
        _FakePlanner(plan),
        retriever,
        writer,
        acquirer=acquirer,
        config=_config(max_retries=0, max_acquisition_rounds=1),
    )

    result = runtime.run(question, task_id="task-semantic-acquisition-failed")

    assert result.answer.status == "insufficient_evidence"
    assert not result.assessment.sufficient
    assert result.assessment.reason == (
        "Answer model found the supplied evidence insufficient"
    )
    assert result.acquisition_rounds == 1
    assert len(acquirer.calls) == 1
    assert writer.calls == 2
    assert [event.node for event in result.trace].count("acquire_evidence") == 1
    assert [event.node for event in result.trace].count("validate_citations") == 1


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
