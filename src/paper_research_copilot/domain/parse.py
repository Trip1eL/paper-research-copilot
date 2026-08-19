"""Framework-independent PDF parsing quality and provenance models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParserName = Literal["pypdf", "pymupdf"]
ParseQualityStatus = Literal["accepted", "warning", "quarantined"]
ParseRouteAction = Literal[
    "primary_accepted",
    "primary_retained",
    "secondary_selected",
    "structured_fallback_required",
]


class PageTextExtraction(BaseModel):
    """Raw text and page facts emitted by one deterministic extractor."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    text: str
    parser_name: ParserName
    parser_version: str = Field(min_length=1)
    latency_ms: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    image_count: int = Field(ge=0)
    ocr_used: bool = False


class PageQualityFeatures(BaseModel):
    """Auditable deterministic features used by the quality scorer."""

    model_config = ConfigDict(frozen=True)

    char_count: int = Field(ge=0)
    line_count: int = Field(ge=0)
    alphanumeric_ratio: float = Field(ge=0, le=1)
    uppercase_word_ratio: float = Field(ge=0, le=1)
    vowelless_word_ratio: float = Field(ge=0, le=1)
    extended_latin_letter_ratio: float = Field(ge=0, le=1)
    control_char_ratio: float = Field(ge=0, le=1)
    replacement_char_ratio: float = Field(ge=0, le=1)
    private_use_char_ratio: float = Field(ge=0, le=1)
    non_printable_char_ratio: float = Field(ge=0, le=1)
    image_count: int = Field(ge=0)


class PageQualityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0, le=1)
    status: ParseQualityStatus
    features: PageQualityFeatures
    signals: tuple[str, ...] = ()


class PageParseCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    extraction: PageTextExtraction
    quality: PageQualityResult


class PageParseResult(BaseModel):
    """Selected page text plus every candidate and the deterministic route reason."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    text: str
    parser_name: ParserName
    parser_version: str
    quality_score: float = Field(ge=0, le=1)
    quality_status: ParseQualityStatus
    ocr_used: bool = False
    warnings: tuple[str, ...] = ()
    route_action: ParseRouteAction
    selection_reason: str = Field(min_length=5)
    candidates: tuple[PageParseCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_selected_candidate(self) -> "PageParseResult":
        selected = [
            item for item in self.candidates if item.extraction.parser_name == self.parser_name
        ]
        if len(selected) != 1:
            raise ValueError("Page result must contain exactly one selected parser candidate")
        candidate = selected[0]
        if candidate.extraction.page_number != self.page_number:
            raise ValueError("Selected candidate page number does not match page result")
        if candidate.extraction.text != self.text:
            raise ValueError("Selected candidate text does not match page result")
        if candidate.quality.score != self.quality_score:
            raise ValueError("Selected candidate score does not match page result")
        return self


class DocumentParseResult(BaseModel):
    """Shadow-safe parse result; it is not an indexing command."""

    model_config = ConfigDict(frozen=True)

    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_path: str
    page_count: int = Field(ge=1)
    shadow_mode: bool
    parser_versions: dict[ParserName, str]
    total_latency_ms: float = Field(ge=0)
    accepted_pages: int = Field(ge=0)
    warning_pages: int = Field(ge=0)
    quarantined_pages: int = Field(ge=0)
    secondary_selected_pages: int = Field(ge=0)
    pages: tuple[PageParseResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_page_summary(self) -> "DocumentParseResult":
        if len(self.pages) != self.page_count:
            raise ValueError("Document page count does not match page results")
        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != list(range(1, self.page_count + 1)):
            raise ValueError("Document page results must be ordered and contiguous")
        status_counts = {
            status: sum(page.quality_status == status for page in self.pages)
            for status in ("accepted", "warning", "quarantined")
        }
        if (
            self.accepted_pages != status_counts["accepted"]
            or self.warning_pages != status_counts["warning"]
            or self.quarantined_pages != status_counts["quarantined"]
        ):
            raise ValueError("Document quality counts do not match page results")
        return self
