"""Deterministic evaluation contracts for the clarification protocol."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.agent import AgentResult


class ClarificationEvaluationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^CL-[0-9]{3}$")
    question: str = Field(min_length=5)
    expected_rule_id: str = Field(min_length=3)
    clarification_response: str = Field(min_length=2)
    expected_child_answer_status: Literal["answered", "insufficient_evidence"] = "answered"
    rationale: str = Field(min_length=10)


class ClarificationCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    ambiguity_detected: bool
    rule_matched: bool
    prompt_present: bool
    pre_clarification_side_effect_free: bool
    child_reentered_research: bool
    child_answer_behavior_correct: bool
    provenance_valid: bool
    strict_pass: bool


class ClarificationEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int = Field(ge=1)
    strict_pass_rate: float = Field(ge=0, le=1)
    ambiguity_detection_rate: float = Field(ge=0, le=1)
    prompt_presence_rate: float = Field(ge=0, le=1)
    side_effect_free_rate: float = Field(ge=0, le=1)
    child_reentry_rate: float = Field(ge=0, le=1)
    child_answer_behavior_accuracy: float = Field(ge=0, le=1)
    provenance_rate: float = Field(ge=0, le=1)
    cases: tuple[ClarificationCaseResult, ...]


def load_clarification_cases(path: Path) -> tuple[ClarificationEvaluationCase, ...]:
    cases: list[ClarificationEvaluationCase] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        try:
            cases.append(ClarificationEvaluationCase.model_validate_json(line))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(
                f"Invalid clarification case at line {line_number}: {exc}"
            ) from exc
    if not cases:
        raise ValueError("Clarification evaluation dataset must not be empty")
    case_ids = tuple(case.case_id for case in cases)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Clarification evaluation case IDs must be unique")
    return tuple(cases)


def evaluate_clarification_case(
    case: ClarificationEvaluationCase,
    *,
    original_result: AgentResult,
    child_result: AgentResult,
    parent_task_id: str,
    child_parent_task_id: str | None,
    persisted_response: str | None,
) -> ClarificationCaseResult:
    clarification = original_result.clarification
    ambiguity_detected = (
        original_result.screening is not None
        and original_result.screening.decision == "ambiguous"
    )
    rule_matched = (
        ambiguity_detected
        and original_result.screening is not None
        and original_result.screening.rule_id == case.expected_rule_id
        and clarification is not None
        and clarification.rule_id == case.expected_rule_id
    )
    prompt_present = bool(
        clarification is not None
        and clarification.prompt.strip()
        and clarification.required_information
    )
    original_nodes = {event.node for event in original_result.trace}
    pre_clarification_side_effect_free = (
        not original_result.evidence
        and original_result.acquisition_rounds == 0
        and original_result.acquisition is None
        and "retrieve_evidence" not in original_nodes
        and "acquire_evidence" not in original_nodes
    )
    child_nodes = {event.node for event in child_result.trace}
    child_reentered_research = (
        child_result.clarification is None
        and "retrieve_evidence" in child_nodes
        and "write_report" in child_nodes
    )
    child_answer_behavior_correct = (
        child_result.answer.status == case.expected_child_answer_status
    )
    provenance_valid = (
        child_parent_task_id == parent_task_id
        and persisted_response is not None
        and _normalize(persisted_response) == _normalize(case.clarification_response)
    )
    checks = (
        ambiguity_detected,
        rule_matched,
        prompt_present,
        pre_clarification_side_effect_free,
        child_reentered_research,
        child_answer_behavior_correct,
        provenance_valid,
    )
    return ClarificationCaseResult(
        case_id=case.case_id,
        ambiguity_detected=ambiguity_detected,
        rule_matched=rule_matched,
        prompt_present=prompt_present,
        pre_clarification_side_effect_free=pre_clarification_side_effect_free,
        child_reentered_research=child_reentered_research,
        child_answer_behavior_correct=child_answer_behavior_correct,
        provenance_valid=provenance_valid,
        strict_pass=all(checks),
    )


def build_clarification_report(
    results: Sequence[ClarificationCaseResult],
) -> ClarificationEvaluationReport:
    if not results:
        raise ValueError("Clarification evaluation requires at least one result")
    return ClarificationEvaluationReport(
        case_count=len(results),
        strict_pass_rate=_rate(item.strict_pass for item in results),
        ambiguity_detection_rate=_rate(item.ambiguity_detected for item in results),
        prompt_presence_rate=_rate(item.prompt_present for item in results),
        side_effect_free_rate=_rate(
            item.pre_clarification_side_effect_free for item in results
        ),
        child_reentry_rate=_rate(item.child_reentered_research for item in results),
        child_answer_behavior_accuracy=_rate(
            item.child_answer_behavior_correct for item in results
        ),
        provenance_rate=_rate(item.provenance_valid for item in results),
        cases=tuple(results),
    )


def _rate(values: Iterable[bool]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
