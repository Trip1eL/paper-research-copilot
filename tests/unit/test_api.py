from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from paper_research_copilot.agent import (
    AgentEvent,
    AgentResult,
    ClarificationRequest,
    EvidenceAssessment,
    QuestionScreening,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.api import ResearchTaskService, create_app
from paper_research_copilot.config import Settings
from paper_research_copilot.domain import Answer
from paper_research_copilot.storage import (
    InMemoryResearchRepository,
    SqliteResearchRepository,
)

QUESTION = "How does episodic memory improve later attempts?"


def _result(question: str = QUESTION) -> AgentResult:
    plan = ResearchPlan(
        question=question,
        question_type="single_paper",
        rationale="Retrieve the requested mechanism",
        tasks=(
            ResearchTask(
                task_id="T1",
                query="episodic memory later attempts",
                goal="Find direct mechanism evidence",
            ),
        ),
    )
    trace = (
        AgentEvent(
            sequence=1,
            node="plan_research",
            outcome="planned",
            latency_ms=1,
        ),
        AgentEvent(
            sequence=2,
            node="write_report",
            outcome="insufficient_evidence",
            latency_ms=1,
        ),
    )
    return AgentResult(
        question=question,
        plan=plan,
        evidence=(),
        assessment=EvidenceAssessment(
            sufficient=False,
            reason="No relevant evidence was retrieved",
            task_candidate_counts={"T1": 0},
            task_selected_counts={"T1": 0},
            missing_task_ids=("T1",),
            distinct_paper_count=0,
            retry_recommended=False,
        ),
        answer=Answer(
            question=question,
            text="INSUFFICIENT_EVIDENCE",
            citations=(),
            status="insufficient_evidence",
        ),
        retry_count=0,
        trace=trace,
    )


class _FakeRuntime:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.closed = False
        self.run_calls: list[tuple[str, str | None]] = []

    def run(
        self,
        question: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
        task_id: str | None = None,
    ) -> AgentResult:
        self.run_calls.append((question, task_id))
        if self.error is not None:
            raise self.error
        result = _result(question)
        if event_callback is not None:
            for event in result.trace:
                event_callback(event)
        return result

    def can_resume(self, task_id: str) -> bool:
        return True

    def resume(
        self,
        task_id: str,
        *,
        event_callback: Callable[[AgentEvent], None] | None = None,
    ) -> AgentResult:
        result = _result()
        if event_callback is not None:
            for event in result.trace:
                event_callback(event)
        return result

    def close(self) -> None:
        self.closed = True


def _clarification_result() -> AgentResult:
    return _result().model_copy(
        update={
            "screening": QuestionScreening(
                decision="ambiguous",
                rule_id="unresolved_reference",
                reason="问题引用了当前请求中不存在的前文对象",
            ),
            "clarification": ClarificationRequest(
                rule_id="unresolved_reference",
                prompt="你指的是哪一篇论文或哪一个方法？",
                required_information=("论文标题、作者、arXiv ID 或明确的方法名称",),
            ),
        }
    )


def _completed_parent(repository: InMemoryResearchRepository, task_id: str) -> None:
    created_at = datetime.now(UTC)
    repository.create_task(task_id=task_id, question=QUESTION, created_at=created_at)
    repository.start_task(task_id, started_at=created_at)
    repository.complete_task(
        task_id,
        status="succeeded",
        completed_at=created_at,
        result_json=_clarification_result().model_dump_json(),
        error=None,
    )


class _FakeCheckpointStore:
    storage_name = "sqlite"

    def __init__(self) -> None:
        self.closed = False

    def has_checkpoint(self, thread_id: str) -> bool:
        return True

    def probe(self) -> tuple[bool, str | None]:
        return True, None

    def close(self) -> None:
        self.closed = True


def _client(runtime: _FakeRuntime, *, frontend_dir: Path | None = None) -> TestClient:
    service = ResearchTaskService(lambda: runtime)
    return TestClient(
        create_app(
            task_service=service,
            settings=Settings(),
            frontend_dir=frontend_dir,
        )
    )


def test_research_task_runs_to_completion_and_streams_ordered_events() -> None:
    runtime = _FakeRuntime()
    with _client(runtime) as client:
        accepted = client.post("/api/v1/research", json={"question": QUESTION})

        assert accepted.status_code == 202
        accepted_payload = accepted.json()
        assert accepted_payload["status"] == "queued"
        task_id = accepted_payload["task_id"]

        stream = client.get(f"/api/v1/research/{task_id}/events")
        task = client.get(f"/api/v1/research/{task_id}")

        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "event: task_queued" in stream.text
        assert stream.text.count("event: agent_node") == 2
        assert "event: task_succeeded" in stream.text
        assert task.status_code == 200
        assert task.json()["status"] == "succeeded"
        assert task.json()["result"]["answer"]["status"] == "insufficient_evidence"
    assert runtime.closed


def test_failed_runtime_is_exposed_as_terminal_task_event() -> None:
    with _client(_FakeRuntime(error=RuntimeError("provider unavailable"))) as client:
        accepted = client.post("/api/v1/research", json={"question": QUESTION}).json()
        task_id = accepted["task_id"]

        stream = client.get(f"/api/v1/research/{task_id}/events")
        task = client.get(f"/api/v1/research/{task_id}").json()

        assert "event: task_failed" in stream.text
        assert task["status"] == "failed"
        assert task["error"] == "RuntimeError: provider unavailable"
        assert task["result"] is None


def test_health_probes_runtime_and_unknown_task_returns_404() -> None:
    runtime = _FakeRuntime()
    with _client(runtime) as client:
        health = client.get("/health")
        missing = client.get("/api/v1/research/not-found")

        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["runtime_ready"] is True
        assert health.json()["qdrant_collection"] == "agent_seed_v3_bge_m3_chunking_v1"
        assert health.json()["dynamic_qdrant_collection"] == (
            "paper_dynamic_bge_m3_chunking_v1"
        )
        assert health.json()["dynamic_acquisition_enabled"] is False
        assert health.json()["claim_verification_enabled"] is True
        assert missing.status_code == 404


def test_request_contract_rejects_short_or_unknown_fields() -> None:
    with _client(_FakeRuntime()) as client:
        short = client.post("/api/v1/research", json={"question": "why"})
        extra = client.post(
            "/api/v1/research",
            json={"question": QUESTION, "model": "override"},
        )

        assert short.status_code == 422
        assert extra.status_code == 422


def test_clarification_creates_linked_child_and_is_idempotent() -> None:
    runtime = _FakeRuntime()
    repository = InMemoryResearchRepository()
    _completed_parent(repository, "ambiguous-parent")
    service = ResearchTaskService(lambda: runtime, repository=repository)

    with TestClient(
        create_app(task_service=service, settings=Settings(), frontend_dir=None)
    ) as client:
        first = client.post(
            "/api/v1/research/ambiguous-parent/clarify",
            json={"response": "ReAct: Synergizing Reasoning and Acting"},
        )
        assert first.status_code == 202
        child_id = first.json()["task_id"]
        client.get(first.json()["events_url"])
        child = client.get(first.json()["task_url"]).json()

        duplicate = client.post(
            "/api/v1/research/ambiguous-parent/clarify",
            json={"response": "  react:   synergizing reasoning and acting  "},
        )

        assert duplicate.status_code == 202
        assert duplicate.json()["task_id"] == child_id
        assert child["parent_task_id"] == "ambiguous-parent"
        assert child["parent_question"] == QUESTION
        assert child["clarification_response"] == (
            "ReAct: Synergizing Reasoning and Acting"
        )
        assert "原研究问题" in child["question"]
        assert "用户补充" in child["question"]
        assert len(runtime.run_calls) == 1


def test_clarification_rejects_missing_nonterminal_and_clear_tasks() -> None:
    runtime = _FakeRuntime()
    repository = InMemoryResearchRepository()
    created_at = datetime.now(UTC)
    repository.create_task(task_id="queued-parent", question=QUESTION, created_at=created_at)
    service = ResearchTaskService(lambda: runtime, repository=repository)

    with TestClient(
        create_app(task_service=service, settings=Settings(), frontend_dir=None)
    ) as client:
        missing = client.post(
            "/api/v1/research/missing/clarify",
            json={"response": "ReAct paper"},
        )
        queued = client.post(
            "/api/v1/research/queued-parent/clarify",
            json={"response": "ReAct paper"},
        )
        normal = client.post("/api/v1/research", json={"question": QUESTION}).json()
        client.get(normal["events_url"])
        clear = client.post(
            f"/api/v1/research/{normal['task_id']}/clarify",
            json={"response": "ReAct paper"},
        )

        assert missing.status_code == 404
        assert queued.status_code == 409
        assert clear.status_code == 409
        assert clear.json()["detail"] == "This task does not request clarification"


def test_interrupted_task_can_be_explicitly_resumed() -> None:
    runtime = _FakeRuntime()
    repository = InMemoryResearchRepository()
    created_at = datetime.now(UTC)
    repository.create_task(task_id="resume-task", question=QUESTION, created_at=created_at)
    repository.start_task("resume-task", started_at=created_at)
    checkpoint_store = _FakeCheckpointStore()
    service = ResearchTaskService(
        lambda: runtime,
        repository=repository,
        checkpoint_store=checkpoint_store,
    )

    with TestClient(
        create_app(task_service=service, settings=Settings(), frontend_dir=None)
    ) as client:
        before = client.get("/api/v1/research/resume-task").json()
        accepted = client.post("/api/v1/research/resume-task/resume")
        stream = client.get("/api/v1/research/resume-task/events?after=3")
        after = client.get("/api/v1/research/resume-task").json()

        assert before["status"] == "interrupted"
        assert accepted.status_code == 202
        assert accepted.json()["status"] == "queued"
        assert "event: task_resumed" in stream.text
        assert "event: task_succeeded" in stream.text
        assert after["status"] == "succeeded"
    assert checkpoint_store.closed


def test_task_result_and_sse_cursor_survive_service_recreation(tmp_path: Path) -> None:
    database_path = tmp_path / "app.db"
    first_service = ResearchTaskService(
        lambda: _FakeRuntime(),
        repository=SqliteResearchRepository(database_path),
    )
    with TestClient(
        create_app(task_service=first_service, settings=Settings(), frontend_dir=None)
    ) as client:
        accepted = client.post("/api/v1/research", json={"question": QUESTION}).json()
        task_id = accepted["task_id"]
        client.get(f"/api/v1/research/{task_id}/events")
        original = client.get(f"/api/v1/research/{task_id}").json()

    second_service = ResearchTaskService(
        lambda: _FakeRuntime(),
        repository=SqliteResearchRepository(database_path),
    )
    with TestClient(
        create_app(task_service=second_service, settings=Settings(), frontend_dir=None)
    ) as client:
        restored = client.get(f"/api/v1/research/{task_id}")
        tail = client.get(
            f"/api/v1/research/{task_id}/events?after={original['event_count'] - 1}"
        )

        assert restored.status_code == 200
        assert restored.json()["result"] == original["result"]
        assert tail.text.count("event: task_succeeded") == 1


def test_built_frontend_is_served_with_spa_fallback(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>Paper Research Copilot</title>",
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("console.log('ready')", encoding="utf-8")

    with _client(_FakeRuntime(), frontend_dir=tmp_path) as client:
        root = client.get("/")
        asset = client.get("/assets/app.js")
        spa_route = client.get("/research/example")
        unknown_api = client.get("/api/v1/not-a-route")

        assert root.status_code == 200
        assert "Paper Research Copilot" in root.text
        assert asset.status_code == 200
        assert asset.text == "console.log('ready')"
        assert spa_route.status_code == 200
        assert spa_route.text == root.text
        assert unknown_api.status_code == 404
        assert unknown_api.headers["content-type"].startswith("application/json")
