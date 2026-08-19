"""Versioned corpus definitions and validated local paper assets."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CorpusPaperSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    arxiv_id: str
    arxiv_version: str
    slug: str
    title: str
    topics: tuple[str, ...]
    source_url: str


class CorpusSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    corpus_id: str
    version: int = Field(ge=1)
    created_on: str
    description: str
    papers: tuple[CorpusPaperSpec, ...]


class CorpusManifestRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    corpus_id: str
    corpus_version: int = Field(ge=1)
    paper_id: str
    arxiv_id: str
    arxiv_version: str
    slug: str
    title: str
    topics: tuple[str, ...]
    source_url: str
    local_path: str
    file_size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    extracted_char_count: int = Field(gt=0)
    parse_status: Literal["verified", "warning", "failed"]
    warnings: tuple[str, ...] = ()


class CorpusPaperAsset(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    spec: CorpusPaperSpec
    manifest: CorpusManifestRecord
    pdf_path: Path


class CorpusCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    spec: CorpusSpec
    papers: tuple[CorpusPaperAsset, ...]
