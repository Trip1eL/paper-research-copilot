"""Final answer returned by the base RAG pipeline."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain.evidence import Citation


class Answer(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str = Field(min_length=1)
    text: str = Field(min_length=1)
    citations: tuple[Citation, ...]
    status: Literal["answered", "insufficient_evidence"] = "answered"
