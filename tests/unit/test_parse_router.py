from pathlib import Path

import pytest

from paper_research_copilot.domain import PageTextExtraction, PaperMetadata, ParserName
from paper_research_copilot.ingestion import (
    FastParserRouter,
    PageAwareChunker,
    ParseQualityGateError,
    PdfExtractionError,
    build_indexable_document,
)


class _FakeExtractor:
    def __init__(
        self,
        parser_name: ParserName,
        pages: tuple[PageTextExtraction, ...],
    ) -> None:
        self._parser_name = parser_name
        self._pages = pages
        self.calls = 0

    @property
    def parser_name(self) -> ParserName:
        return self._parser_name

    @property
    def parser_version(self) -> str:
        return "test"

    def extract(self, path: Path) -> tuple[PageTextExtraction, ...]:
        self.calls += 1
        return self._pages


def _page(text: str, parser_name: ParserName, *, page_number: int = 1) -> PageTextExtraction:
    return PageTextExtraction(
        page_number=page_number,
        text=text,
        parser_name=parser_name,
        parser_version="test",
        latency_ms=1,
        width=612,
        height=792,
        image_count=0,
    )


def _pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-router-test")
    return path


def test_router_retains_accepted_primary_even_in_shadow_mode(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("clean text " * 100, "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("alternative text " * 100, "pymupdf"),))

    result = FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True)

    assert result.pages[0].parser_name == "pypdf"
    assert result.pages[0].route_action == "primary_accepted"
    assert len(result.pages[0].candidates) == 2
    assert primary.calls == secondary.calls == 1


def test_router_skips_secondary_when_primary_is_accepted_outside_shadow(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("clean text " * 100, "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("alternative " * 100, "pymupdf"),))

    result = FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=False)

    assert result.pages[0].route_action == "primary_accepted"
    assert len(result.pages[0].candidates) == 1
    assert secondary.calls == 0


def test_router_selects_materially_better_secondary(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page(("bad " * 100) + ("\x03" * 100), "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("clean recovered text " * 100, "pymupdf"),))

    result = FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True)
    page = result.pages[0]

    assert page.parser_name == "pymupdf"
    assert page.route_action == "secondary_selected"
    assert page.quality_status == "accepted"
    assert result.secondary_selected_pages == 1


def test_router_requires_structured_fallback_when_both_are_empty(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("", "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("", "pymupdf"),))

    page = (
        FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True).pages[0]
    )

    assert page.quality_status == "quarantined"
    assert page.route_action == "structured_fallback_required"
    assert "structured_fallback_required" in page.warnings


def test_quality_gate_blocks_quarantined_pages_from_chunking(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("", "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("", "pymupdf"),))
    routed = FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True)
    metadata = PaperMetadata(
        document_sha256=routed.document_sha256,
        title="Blocked Paper",
        source_path=routed.source_path,
        page_count=1,
    )

    with pytest.raises(ParseQualityGateError, match="cannot enter chunking"):
        build_indexable_document(metadata, routed)


def test_quality_gate_propagates_parse_provenance_to_chunks(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("clean evidence " * 100, "pypdf"),))
    secondary = _FakeExtractor("pymupdf", (_page("alternative " * 100, "pymupdf"),))
    routed = FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True)
    metadata = PaperMetadata(
        document_sha256=routed.document_sha256,
        title="Indexable Paper",
        source_path=routed.source_path,
        page_count=1,
    )

    document = build_indexable_document(metadata, routed)
    chunks = PageAwareChunker(chunk_size=400, overlap=40).split(document)

    assert chunks
    assert all(chunk.parser_name == "pypdf" for chunk in chunks)
    assert all(chunk.parser_version == "test" for chunk in chunks)
    assert all(chunk.parse_quality_status == "accepted" for chunk in chunks)
    assert all(chunk.parse_quality_score == 1 for chunk in chunks)


def test_router_rejects_extractor_page_count_mismatch(tmp_path: Path) -> None:
    primary = _FakeExtractor("pypdf", (_page("short", "pypdf"),))
    secondary = _FakeExtractor(
        "pymupdf",
        (
            _page("clean " * 100, "pymupdf"),
            _page("clean " * 100, "pymupdf", page_number=2),
        ),
    )

    with pytest.raises(PdfExtractionError, match="different page counts"):
        FastParserRouter(primary, secondary).parse(_pdf_path(tmp_path), shadow_mode=True)
