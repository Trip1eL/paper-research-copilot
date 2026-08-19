"""Boundary implemented by heavyweight structured document parsers."""

from pathlib import Path
from typing import Protocol

from paper_research_copilot.domain.structured_parse import (
    StructuredPageResult,
    StructuredParseMethod,
)


class StructuredDocumentParser(Protocol):
    parser_name: str
    parser_version: str

    def parse_page(
        self,
        path: Path,
        *,
        page_number: int,
        output_dir: Path,
        method: StructuredParseMethod,
    ) -> StructuredPageResult: ...
