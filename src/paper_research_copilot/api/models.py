"""Public Pydantic contracts for the research task API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from paper_research_copilot.agent import AgentEvent, AgentResult

ResearchTaskStatus = Literal["queued", "running", "succeeded", "failed"]
ResearchEventType = Literal[
    "task_queued",
    "task_started",
    "agent_node",
    "task_succeeded",
    "task_failed",
]


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=5, max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 5:
            raise ValueError("Research question must contain at least five characters")
        return normalized


class ResearchTaskAccepted(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    status: ResearchTaskStatus
    created_at: datetime
    task_url: str
    events_url: str


class ResearchTaskView(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    question: str
    status: ResearchTaskStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    event_count: int = Field(ge=1)
    result: AgentResult | None = None
    error: str | None = None


class ResearchStreamEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int = Field(ge=1)
    event_type: ResearchEventType
    task_id: str
    created_at: datetime
    status: ResearchTaskStatus
    agent_event: AgentEvent | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "degraded"]
    service: str = "paper-research-copilot"
    runtime_ready: bool
    runtime_error: str | None = None
    corpus_version: int
    qdrant_collection: str
    task_store: Literal["memory"] = "memory"
    queued_tasks: int = Field(ge=0)
    running_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
