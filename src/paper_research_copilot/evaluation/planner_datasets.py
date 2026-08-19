"""Versioned, human-reviewable datasets for Planner and Router evaluation."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PlannerQuestionType = Literal["single_paper", "cross_paper"]
PlannerCaseCategory = Literal[
    "single_lookup",
    "cross_comparison",
    "multi_method_synthesis",
    "corpus_verification",
    "routing_boundary",
]


class PlannerExpectedFacet(BaseModel):
    model_config = ConfigDict(frozen=True)

    facet_id: str = Field(pattern=r"^F[1-4]$")
    description: str = Field(min_length=3)
    match_any: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_aliases(self) -> "PlannerExpectedFacet":
        aliases = tuple(alias.strip().casefold() for alias in self.match_any)
        if any(not alias for alias in aliases):
            raise ValueError("Planner facet aliases must not be empty")
        if len(aliases) != len(set(aliases)):
            raise ValueError("Planner facet aliases must be unique")
        return self


class PlannerRoutingCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^PR-[0-9]{3}$")
    source_case_id: str | None = Field(default=None, pattern=r"^(DS|AE)-[0-9]{3}$")
    category: PlannerCaseCategory
    difficulty: Literal["medium", "hard"]
    question: str = Field(min_length=5)
    expected_question_type: PlannerQuestionType
    acceptable_question_types: tuple[PlannerQuestionType, ...] = Field(min_length=1)
    expected_task_count: int = Field(ge=1, le=4)
    acceptable_task_counts: tuple[int, ...] = Field(min_length=1)
    expected_facets: tuple[PlannerExpectedFacet, ...] = Field(min_length=1, max_length=4)
    label_sensitive: bool = False
    annotation_notes: str = Field(min_length=5)

    @model_validator(mode="after")
    def validate_routing_contract(self) -> "PlannerRoutingCase":
        if self.expected_question_type not in self.acceptable_question_types:
            raise ValueError("Expected question type must be acceptable")
        if self.expected_task_count not in self.acceptable_task_counts:
            raise ValueError("Expected task count must be acceptable")
        if len(set(self.acceptable_question_types)) != len(self.acceptable_question_types):
            raise ValueError("Acceptable question types must be unique")
        if len(set(self.acceptable_task_counts)) != len(self.acceptable_task_counts):
            raise ValueError("Acceptable task counts must be unique")
        if any(count < 1 or count > 4 for count in self.acceptable_task_counts):
            raise ValueError("Acceptable task counts must be between one and four")
        if self.expected_question_type == "single_paper" and self.expected_task_count != 1:
            raise ValueError("Strict single_paper labels require one task")
        if self.expected_question_type == "cross_paper" and self.expected_task_count < 2:
            raise ValueError("Strict cross_paper labels require at least two tasks")
        if (
            "single_paper" in self.acceptable_question_types
            and 1 not in self.acceptable_task_counts
        ):
            raise ValueError("Acceptable single_paper routes require task count one")
        if "cross_paper" in self.acceptable_question_types and not any(
            count >= 2 for count in self.acceptable_task_counts
        ):
            raise ValueError("Acceptable cross_paper routes require a multi-task count")
        if not self.label_sensitive and self.acceptable_question_types != (
            self.expected_question_type,
        ):
            raise ValueError("Only label-sensitive cases may declare alternative routes")
        facet_ids = [facet.facet_id for facet in self.expected_facets]
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("Planner facet IDs must be unique within a case")
        return self


def load_planner_routing_cases(
    path: Path,
    *,
    source_questions: Mapping[str, str] | None = None,
) -> tuple[PlannerRoutingCase, ...]:
    cases = tuple(
        PlannerRoutingCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Planner routing dataset is empty")
    case_ids = [case.case_id for case in cases]
    questions = [" ".join(case.question.casefold().split()) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Planner routing dataset contains duplicate Case IDs")
    if len(questions) != len(set(questions)):
        raise ValueError("Planner routing dataset contains duplicate questions")
    if source_questions is not None:
        unknown = sorted(
            {
                case.source_case_id
                for case in cases
                if case.source_case_id is not None and case.source_case_id not in source_questions
            }
        )
        if unknown:
            raise ValueError(f"Planner dataset contains unknown source Case IDs: {unknown}")
        mismatches = [
            case.case_id
            for case in cases
            if case.source_case_id is not None
            and case.question != source_questions[case.source_case_id]
        ]
        if mismatches:
            raise ValueError(f"Planner dataset changed source questions: {mismatches}")
    return cases
