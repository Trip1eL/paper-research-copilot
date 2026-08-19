"""Framework-independent models for bounded academic paper acquisition."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AcademicProvider = Literal["arxiv"]
PaperAssetStatus = Literal[
    "discovered",
    "downloaded",
    "parsed",
    "indexed",
    "active",
    "duplicate",
    "download_failed",
    "quarantined",
    "indexing_failed",
]
AcquisitionStatus = Literal["running", "succeeded", "partial", "failed"]


class PaperCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: AcademicProvider = "arxiv"
    external_id: str = Field(min_length=5, max_length=80)
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=1000)
    authors: tuple[str, ...] = ()
    abstract: str = Field(min_length=1)
    published_at: datetime
    updated_at: datetime
    landing_url: str
    pdf_url: str
    doi: str | None = None
    categories: tuple[str, ...] = ()
    search_score: float = Field(default=0, ge=0)

    @field_validator("title", "abstract")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("authors", "categories")
    @classmethod
    def normalize_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in value if item.strip())

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None

    @model_validator(mode="after")
    def validate_urls_and_dates(self) -> PaperCandidate:
        for name, value in (("landing_url", self.landing_url), ("pdf_url", self.pdf_url)):
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError(f"{name} must be an absolute HTTPS URL")
        if self.published_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Candidate timestamps must be timezone-aware")
        return self

    @property
    def identity(self) -> str:
        return f"{self.provider}:{self.external_id}v{self.revision}"

    @property
    def asset_id(self) -> str:
        return uuid5(NAMESPACE_URL, self.identity).hex


class DownloadedPaper(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    local_path: str
    file_size_bytes: int = Field(gt=0)
    content_type: str
    downloaded_at: datetime
    reused_local_file: bool = False


class PaperAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    candidate: PaperCandidate
    acquisition_query: str
    status: PaperAssetStatus
    created_at: datetime
    updated_at: datetime
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    local_path: str | None = None
    file_size_bytes: int | None = Field(default=None, gt=0)
    page_count: int | None = Field(default=None, ge=1)
    chunk_count: int | None = Field(default=None, ge=0)
    collection_name: str | None = None
    index_version: str | None = None
    parse_summary_json: str | None = None
    duplicate_of_asset_id: str | None = None
    error: str | None = None


class AcquisitionBudget(BaseModel):
    model_config = ConfigDict(frozen=True)

    search_queries: int = Field(default=1, ge=1, le=2)
    candidates_per_query: int = Field(default=5, ge=1, le=10)
    max_downloads: int = Field(default=2, ge=1, le=5)
    max_pdf_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    max_dynamic_chunks: int = Field(default=500, ge=1, le=2000)


class AcquisitionRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    acquisition_id: str
    task_id: str | None = None
    query: str
    status: AcquisitionStatus
    budget: AcquisitionBudget
    candidate_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    downloaded_count: int = Field(default=0, ge=0)
    indexed_count: int = Field(default=0, ge=0)
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class DynamicIngestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset: PaperAsset
    outcome: Literal["indexed", "already_active", "duplicate", "failed"]
    downloaded: bool = False
    embedded: bool


class DynamicParseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)
    accepted_pages: int = Field(ge=0)
    warning_pages: int = Field(ge=0)
    quarantined_pages: int = Field(ge=0)
    secondary_selected_pages: int = Field(ge=0)
    parser_versions: dict[str, str]


class AcquisitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run: AcquisitionRun
    candidates: tuple[PaperCandidate, ...]
    ingestions: tuple[DynamicIngestionResult, ...]
