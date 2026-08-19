"""Framework-independent structured parsing and block provenance models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StructuredBlockType = Literal[
    "title",
    "paragraph",
    "list",
    "table",
    "formula",
    "figure",
    "caption",
    "code",
    "unknown",
]
StructuredParseMethod = Literal["auto", "txt", "ocr"]


class StructuredContentBlock(BaseModel):
    """One page-aware block normalized from a structured parser output."""

    model_config = ConfigDict(frozen=True)

    block_id: str = Field(pattern=r"^p[0-9]{4}-b[0-9]{4}$")
    page_number: int = Field(ge=1)
    block_type: StructuredBlockType
    text: str = ""
    html: str | None = None
    bbox: tuple[int, int, int, int] | None = None
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    ocr_used: bool | None = None

    @model_validator(mode="after")
    def validate_bbox(self) -> "StructuredContentBlock":
        if self.bbox is None:
            return self
        x0, y0, x1, y1 = self.bbox
        if not all(0 <= value <= 1000 for value in self.bbox):
            raise ValueError("Structured block bbox coordinates must be normalized to 0..1000")
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Structured block bbox must have positive width and height")
        return self


class StructuredPageResult(BaseModel):
    """Structured parsing result for one original PDF page."""

    model_config = ConfigDict(frozen=True)

    source_path: str
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(ge=1)
    parser_name: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    parse_method: StructuredParseMethod
    device: str = Field(min_length=1)
    latency_ms: float = Field(ge=0)
    markdown: str
    blocks: tuple[StructuredContentBlock, ...]
    raw_output_dir: str

    @model_validator(mode="after")
    def validate_block_pages(self) -> "StructuredPageResult":
        if any(block.page_number != self.page_number for block in self.blocks):
            raise ValueError("Structured block page numbers must match the page result")
        return self
