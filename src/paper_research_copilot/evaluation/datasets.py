"""Schemas and validation for human-reviewable retrieval diagnostics."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RelevantPages(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    pages: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pages(self) -> "RelevantPages":
        if any(page < 1 for page in self.pages):
            raise ValueError("Relevant page numbers must be positive")
        if len(set(self.pages)) != len(self.pages):
            raise ValueError("Relevant page numbers must be unique")
        return self


class RetrievalDiagnosticCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str = Field(pattern=r"^(?:RD|DS)-[0-9]{3}$")
    question: str = Field(min_length=5)
    question_type: Literal["fact", "method", "comparison", "cross_paper"]
    difficulty: Literal["easy", "medium", "hard"]
    subset: Literal["known_paper", "discovery"] = "known_paper"
    contains_paper_name: bool = True
    hard_negative: bool = False
    relevant: tuple[RelevantPages, ...] = Field(min_length=1)
    evidence_hint: str = Field(min_length=5)
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_relevant_papers(self) -> "RetrievalDiagnosticCase":
        paper_ids = [item.paper_id for item in self.relevant]
        if len(set(paper_ids)) != len(paper_ids):
            raise ValueError("Relevant paper IDs must be unique within a case")
        if self.question_type == "cross_paper" and len(paper_ids) < 2:
            raise ValueError("A cross_paper case requires at least two papers")
        if self.subset == "discovery" and self.contains_paper_name:
            raise ValueError("A discovery case must not declare contains_paper_name=true")
        return self


def load_retrieval_diagnostics(
    path: Path,
    *,
    allowed_paper_ids: set[str] | None = None,
    paper_page_counts: dict[str, int] | None = None,
    paper_aliases: dict[str, tuple[str, ...]] | None = None,
) -> tuple[RetrievalDiagnosticCase, ...]:
    cases = tuple(
        RetrievalDiagnosticCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Diagnostic dataset contains duplicate case IDs")
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
            raise ValueError(f"Diagnostic dataset contains unknown paper IDs: {unknown}")
    if paper_page_counts is not None:
        out_of_range = [
            f"{case.case_id}:{relevant.paper_id}:p{page}"
            for case in cases
            for relevant in case.relevant
            for page in relevant.pages
            if page > paper_page_counts[relevant.paper_id]
        ]
        if out_of_range:
            raise ValueError(f"Diagnostic dataset contains out-of-range pages: {out_of_range}")
    if paper_aliases is not None:
        leaked_names = [
            f"{case.case_id}:{alias}"
            for case in cases
            if case.subset == "discovery"
            for relevant in case.relevant
            for alias in paper_aliases.get(relevant.paper_id, ())
            if alias.strip() and alias.casefold() in case.question.casefold()
        ]
        if leaked_names:
            raise ValueError(f"Discovery questions contain target paper names: {leaked_names}")
    return cases
