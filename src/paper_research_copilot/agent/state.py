"""LangGraph state shared by all first-version Agent nodes."""

from typing import TypedDict

from paper_research_copilot.agent.models import (
    AgentAcquisitionSummary,
    AgentEvent,
    EvidenceAssessment,
    ResearchPlan,
)
from paper_research_copilot.domain import Answer, RetrievedChunk


class ResearchState(TypedDict, total=False):
    question: str
    task_id: str | None
    plan: ResearchPlan
    rankings_by_task: dict[str, tuple[RetrievedChunk, ...]]
    evidence: tuple[RetrievedChunk, ...]
    task_candidate_counts: dict[str, int]
    task_selected_counts: dict[str, int]
    assessment: EvidenceAssessment
    retry_count: int
    acquisition_rounds: int
    acquisition: AgentAcquisitionSummary | None
    answer: Answer
    trace: tuple[AgentEvent, ...]
