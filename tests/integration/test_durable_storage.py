from datetime import UTC, datetime, timedelta

import pytest

from paper_research_copilot.agent import AgentEvent
from paper_research_copilot.storage import (
    SqliteResearchRepository,
    TaskStateConflictError,
)

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


def test_sqlite_repository_persists_result_events_and_cursor(tmp_path) -> None:
    path = tmp_path / "app.db"
    repository = SqliteResearchRepository(path)
    repository.create_task(task_id="task-1", question="What changed?", created_at=NOW)
    repository.start_task("task-1", started_at=NOW + timedelta(seconds=1))
    event = AgentEvent(
        sequence=1,
        node="plan_research",
        outcome="planned",
        latency_ms=1,
    )
    repository.append_agent_event(
        "task-1",
        created_at=NOW + timedelta(seconds=2),
        agent_event_json=event.model_dump_json(),
        current_node=event.node,
    )
    repository.complete_task(
        "task-1",
        status="succeeded",
        completed_at=NOW + timedelta(seconds=3),
        result_json='{"answer":"persisted"}',
        error=None,
    )
    repository.close()

    reopened = SqliteResearchRepository(path)
    task = reopened.get_task("task-1")
    later_events = reopened.list_events("task-1", after_sequence=2)

    assert task.status == "succeeded"
    assert task.result_json == '{"answer":"persisted"}'
    assert task.event_count == 4
    assert [item.sequence for item in later_events] == [3, 4]
    assert later_events[0].agent_event_json == event.model_dump_json()
    assert later_events[1].event_type == "task_succeeded"
    reopened.close()


def test_running_task_is_interrupted_then_can_be_queued_for_resume(tmp_path) -> None:
    path = tmp_path / "app.db"
    repository = SqliteResearchRepository(path)
    repository.create_task(task_id="task-2", question="Resume me", created_at=NOW)
    repository.start_task("task-2", started_at=NOW + timedelta(seconds=1))
    repository.close()

    reopened = SqliteResearchRepository(path)
    interrupted = reopened.interrupt_running_tasks(
        interrupted_at=NOW + timedelta(seconds=2)
    )
    assert interrupted == ("task-2",)
    assert reopened.get_task("task-2").status == "interrupted"
    assert reopened.list_events("task-2")[-1].event_type == "task_interrupted"

    resumed = reopened.resume_task("task-2", resumed_at=NOW + timedelta(seconds=3))
    started = reopened.start_task("task-2", started_at=NOW + timedelta(seconds=4))
    assert resumed.status == "queued"
    assert started.status == "running"
    assert started.attempt == 2
    assert [event.event_type for event in reopened.list_events("task-2")][-2:] == [
        "task_resumed",
        "task_started",
    ]
    with pytest.raises(TaskStateConflictError):
        reopened.resume_task("task-2", resumed_at=NOW + timedelta(seconds=5))
    reopened.close()


def test_alembic_upgrade_is_idempotent(tmp_path) -> None:
    path = tmp_path / "app.db"
    SqliteResearchRepository(path).close()
    SqliteResearchRepository(path).close()

