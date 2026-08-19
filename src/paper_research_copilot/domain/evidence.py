"""Retrieved evidence and citation domain models."""

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain.paper import PaperChunk


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    citation_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    score: float
    chunk: PaperChunk


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    citation_id: str = Field(pattern=r"^C[1-9][0-9]*$")
    chunk_id: str
    paper_id: str | None = None
    title: str
    source_path: str
    page_number: int = Field(ge=1)
    excerpt: str
    retrieval_score: float
