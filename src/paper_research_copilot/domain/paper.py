"""Paper parsing and chunking domain models."""

from pydantic import BaseModel, ConfigDict, Field


class PaperMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    authors: tuple[str, ...] = ()
    source_path: str
    page_count: int = Field(ge=1)


class ParsedPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    text: str


class ParsedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    metadata: PaperMetadata
    pages: tuple[ParsedPage, ...]


class ChunkContext(BaseModel):
    """Versioned corpus identity attached to every corpus-backed chunk."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    corpus_version: int = Field(ge=1)
    paper_id: str
    arxiv_id: str
    arxiv_version: str


class PaperChunk(BaseModel):
    """A page-bounded piece of paper text with stable citation metadata."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_index: int = Field(ge=0)
    chunking_version: str
    corpus_id: str | None = None
    corpus_version: int | None = Field(default=None, ge=1)
    paper_id: str | None = None
    arxiv_id: str | None = None
    arxiv_version: str | None = None
    title: str
    source_path: str
    page_number: int = Field(ge=1)
    section_title: str | None = None
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str = Field(min_length=1)


class IngestionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_count: int = Field(ge=0)
    page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    collection_name: str | None = None
    corpus_id: str | None = None
    corpus_version: int | None = Field(default=None, ge=1)
