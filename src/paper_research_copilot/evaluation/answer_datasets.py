"""Schemas and validation for human-reviewable answer evaluation cases."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.evaluation.datasets import RelevantPages


class AnswerKeyPoint(BaseModel):
    """One reference fact with lexical aliases for deterministic coverage checks."""

    model_config = ConfigDict(frozen=True)

    key_point_id: str = Field(pattern=r"^KP-[0-9]{2}$")
    description: str = Field(min_length=3)
    match_any: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_aliases(self) -> "AnswerKeyPoint":
        normalized = [alias.strip().casefold() for alias in self.match_any]
        if any(not alias for alias in normalized):
            raise ValueError("Key-point aliases must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Key-point aliases must be unique")
        return self


class AnswerEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^AE-[0-9]{3}$")
    source_case_id: str | None = Field(default=None, pattern=r"^DS-[0-9]{3}$")
    question: str = Field(min_length=5)
    question_type: Literal["fact", "method", "comparison", "cross_paper", "unanswerable"]
    difficulty: Literal["easy", "medium", "hard"]
    answerable: bool = True
    relevant: tuple[RelevantPages, ...] = ()
    reference_answer: str | None = None
    key_points: tuple[AnswerKeyPoint, ...] = ()
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_answer_contract(self) -> "AnswerEvaluationCase":
        paper_ids = [item.paper_id for item in self.relevant]
        key_point_ids = [item.key_point_id for item in self.key_points]
        if len(set(paper_ids)) != len(paper_ids):
            raise ValueError("Relevant paper IDs must be unique within a case")
        if len(set(key_point_ids)) != len(key_point_ids):
            raise ValueError("Key-point IDs must be unique within a case")
        if self.answerable:
            if not self.relevant or not self.reference_answer or not self.key_points:
                raise ValueError(
                    "Answerable cases require relevant sources, a reference answer, and key points"
                )
            if self.question_type == "unanswerable":
                raise ValueError("An answerable case cannot use question_type=unanswerable")
        elif self.relevant or self.reference_answer or self.key_points:
            raise ValueError("Unanswerable cases must not declare gold evidence or answer content")
        elif self.question_type != "unanswerable":
            raise ValueError("An unanswerable case must use question_type=unanswerable")
        return self


def load_answer_evaluation_cases(
    path: Path,
    *,
    allowed_paper_ids: set[str] | None = None,
    paper_page_counts: dict[str, int] | None = None,
) -> tuple[AnswerEvaluationCase, ...]:
    cases = tuple(
        AnswerEvaluationCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    case_ids = [case.case_id for case in cases]
    if not cases:
        raise ValueError("Answer evaluation dataset is empty")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Answer evaluation dataset contains duplicate case IDs")
    if allowed_paper_ids is not None:
        unknown = sorted(
            {
                relevant.paper_id
                for case in cases
                for relevant in case.relevant
                if relevant.paper_id not in allowed_paper_ids
            }
        )
        if unknown:
            raise ValueError(f"Answer dataset contains unknown paper IDs: {unknown}")
    if paper_page_counts is not None:
        out_of_range = [
            f"{case.case_id}:{relevant.paper_id}:p{page}"
            for case in cases
            for relevant in case.relevant
            for page in relevant.pages
            if page > paper_page_counts[relevant.paper_id]
        ]
        if out_of_range:
            raise ValueError(f"Answer dataset contains out-of-range pages: {out_of_range}")
    return cases
