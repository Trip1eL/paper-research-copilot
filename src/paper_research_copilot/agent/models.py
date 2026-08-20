"""Structured contracts for the first research Agent runtime."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.domain import AcquisitionStatus, Answer, RetrievedChunk
from paper_research_copilot.integrations import ChatTokenUsage

QuestionType = Literal["single_paper", "cross_paper"]


class ClarificationRequest(BaseModel):
    """Structured information needed before research can proceed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=3)
    prompt: str = Field(min_length=5)
    required_information: tuple[str, ...] = Field(min_length=1)


class QuestionScreening(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Literal["clear", "ambiguous"]
    rule_id: str | None = None
    reason: str = Field(min_length=5)


class ResearchTask(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(pattern=r"^T[1-4]$")
    query: str = Field(min_length=5)
    goal: str = Field(min_length=5)


class ResearchPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=5)
    question_type: QuestionType
    rationale: str = Field(min_length=5)
    tasks: tuple[ResearchTask, ...] = Field(min_length=1, max_length=4)
    revision: int = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def validate_task_shape(self) -> "ResearchPlan":
        expected_count = 1 if self.question_type == "single_paper" else None
        if expected_count is not None and len(self.tasks) != expected_count:
            raise ValueError("single_paper plans require exactly one Research Task")
        if self.question_type == "cross_paper" and len(self.tasks) < 2:
            raise ValueError("cross_paper plans require between two and four Research Tasks")
        expected_ids = tuple(f"T{index}" for index in range(1, len(self.tasks) + 1))
        if tuple(task.task_id for task in self.tasks) != expected_ids:
            raise ValueError("Research Task IDs must be consecutive and start at T1")
        normalized_queries = tuple(" ".join(task.query.casefold().split()) for task in self.tasks)
        if len(normalized_queries) != len(set(normalized_queries)):
            raise ValueError("Research Task queries must be unique")
        if self.question_type == "cross_paper" and any(
            query == " ".join(self.question.casefold().split()) for query in normalized_queries
        ):
            raise ValueError("cross_paper tasks must decompose rather than repeat the question")
        return self


class PlanningResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan: ResearchPlan
    operation: Literal["initial", "revision"]
    model: str
    prompt_version: str
    cache_hit: bool
    latency_ms: float = Field(ge=0)
    generation_latency_ms: float = Field(ge=0)
    attempts: int = Field(default=1, ge=1)
    repair_attempts: int = Field(default=0, ge=0)
    fallback_used: bool = False
    fallback_reason: str | None = None
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    response_model: str | None = None


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    sufficient: bool
    reason: str = Field(min_length=5)
    task_candidate_counts: dict[str, int]
    task_selected_counts: dict[str, int]
    missing_task_ids: tuple[str, ...] = ()
    distinct_paper_count: int = Field(ge=0)
    retry_recommended: bool


class AgentEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int = Field(ge=1)
    node: str = Field(min_length=2)
    outcome: str = Field(min_length=2)
    latency_ms: float = Field(ge=0)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class AgentAcquisitionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    acquisition_id: str | None = None
    status: AcquisitionStatus
    candidate_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    downloaded_count: int = Field(default=0, ge=0)
    indexed_count: int = Field(default=0, ge=0)
    asset_ids: tuple[str, ...] = ()
    paper_titles: tuple[str, ...] = ()
    error: str | None = None


class ClaimAssessment(BaseModel):
    """Support judgment for one material claim in the generated answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str = Field(pattern=r"^CL[1-8]$")
    claim: str = Field(min_length=1)
    citation_ids: tuple[str, ...]
    verdict: Literal["supported", "partially_supported", "unsupported"]
    rationale: str = Field(min_length=1)


class ClaimVerification(BaseModel):
    """Bounded production verification result, independent of evaluation gold data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["passed", "revised", "skipped", "error"]
    claims: tuple[ClaimAssessment, ...] = Field(default=(), max_length=8)
    rationale: str = Field(min_length=1)
    needs_human_review: bool = False
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: float = Field(default=0, ge=0)
    attempts: int = Field(default=0, ge=0)
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    response_model: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_status_contract(self) -> "ClaimVerification":
        if self.status in {"passed", "revised"} and not self.claims:
            raise ValueError("Completed Claim Verification requires at least one Claim")
        if self.status == "error" and (not self.needs_human_review or not self.error):
            raise ValueError("Claim Verification errors require an error and human review")
        return self


class AgentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    screening: QuestionScreening | None = None
    clarification: ClarificationRequest | None = None
    plan: ResearchPlan
    evidence: tuple[RetrievedChunk, ...]
    assessment: EvidenceAssessment
    answer: Answer
    retry_count: int = Field(ge=0)
    acquisition_rounds: int = Field(default=0, ge=0, le=1)
    acquisition: AgentAcquisitionSummary | None = None
    verification: ClaimVerification | None = None
    trace: tuple[AgentEvent, ...]

    @model_validator(mode="after")
    def validate_clarification(self) -> "AgentResult":
        if self.clarification is None:
            return self
        if self.screening is None or self.screening.decision != "ambiguous":
            raise ValueError("Clarification requires an ambiguous Question Screening")
        if self.screening.rule_id != self.clarification.rule_id:
            raise ValueError("Clarification Rule must match Question Screening Rule")
        return self


class AgentRuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    top_k: int = Field(default=10, ge=1, le=20)
    candidate_pool_per_task: int = Field(default=30, ge=1, le=100)
    max_retries: int = Field(default=1, ge=0, le=1)
    max_acquisition_rounds: int = Field(default=0, ge=0, le=1)
    min_chunks_per_task: int = Field(default=2, ge=1, le=5)

    @model_validator(mode="after")
    def validate_candidate_pool(self) -> "AgentRuntimeConfig":
        if self.candidate_pool_per_task < self.top_k:
            raise ValueError("Agent candidate pool must be at least Top-K")
        return self
