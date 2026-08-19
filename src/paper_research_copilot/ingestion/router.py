"""Page-level fast parser selection with an explicit structured fallback boundary."""

import hashlib
from pathlib import Path

from paper_research_copilot.domain import (
    DocumentParseResult,
    PageParseCandidate,
    PageParseResult,
    PageTextExtraction,
    PaperMetadata,
    ParsedDocument,
    ParsedPage,
    ParseRouteAction,
)
from paper_research_copilot.ingestion.extractors import (
    PdfExtractionError,
    PdfTextExtractor,
    PyMuPdfExtractor,
    PypdfExtractor,
)
from paper_research_copilot.ingestion.quality import PageQualityScorer


class FastParserRouter:
    """Prefer pypdf, compare PyMuPDF when needed, and quarantine unresolved pages."""

    def __init__(
        self,
        primary: PdfTextExtractor | None = None,
        secondary: PdfTextExtractor | None = None,
        scorer: PageQualityScorer | None = None,
        *,
        minimum_secondary_improvement: float = 0.05,
    ) -> None:
        if not 0 <= minimum_secondary_improvement <= 1:
            raise ValueError("minimum_secondary_improvement must be between 0 and 1")
        self.primary = primary or PypdfExtractor()
        self.secondary = secondary or PyMuPdfExtractor()
        if self.primary.parser_name == self.secondary.parser_name:
            raise ValueError("Primary and secondary extractors must use different parsers")
        self.scorer = scorer or PageQualityScorer()
        self.minimum_secondary_improvement = minimum_secondary_improvement

    def parse(self, path: Path, *, shadow_mode: bool = True) -> DocumentParseResult:
        pdf_path = path.expanduser().resolve()
        primary_pages = self.primary.extract(pdf_path)
        primary_candidates = tuple(self._candidate(page) for page in primary_pages)
        needs_secondary = shadow_mode or any(
            item.quality.status != "accepted" for item in primary_candidates
        )
        secondary_candidates: tuple[PageParseCandidate, ...] = ()
        if needs_secondary:
            secondary_pages = self.secondary.extract(pdf_path)
            if len(secondary_pages) != len(primary_pages):
                raise PdfExtractionError(
                    "Fast extractors returned different page counts: "
                    f"{len(primary_pages)} != {len(secondary_pages)}"
                )
            secondary_candidates = tuple(self._candidate(page) for page in secondary_pages)

        pages = tuple(
            self._select_page(
                primary,
                secondary_candidates[index] if secondary_candidates else None,
            )
            for index, primary in enumerate(primary_candidates)
        )
        parser_versions = {self.primary.parser_name: self.primary.parser_version}
        if secondary_candidates:
            parser_versions[self.secondary.parser_name] = self.secondary.parser_version
        return DocumentParseResult(
            document_sha256=_sha256(pdf_path),
            source_path=str(pdf_path),
            page_count=len(pages),
            shadow_mode=shadow_mode,
            parser_versions=parser_versions,
            total_latency_ms=round(
                sum(
                    candidate.extraction.latency_ms
                    for page in pages
                    for candidate in page.candidates
                ),
                2,
            ),
            accepted_pages=sum(page.quality_status == "accepted" for page in pages),
            warning_pages=sum(page.quality_status == "warning" for page in pages),
            quarantined_pages=sum(page.quality_status == "quarantined" for page in pages),
            secondary_selected_pages=sum(
                page.parser_name == self.secondary.parser_name for page in pages
            ),
            pages=pages,
        )

    def _candidate(self, extraction: PageTextExtraction) -> PageParseCandidate:
        return PageParseCandidate(
            extraction=extraction,
            quality=self.scorer.score(extraction),
        )

    def _select_page(
        self,
        primary: PageParseCandidate,
        secondary: PageParseCandidate | None,
    ) -> PageParseResult:
        action: ParseRouteAction
        if primary.quality.status == "accepted":
            selected = primary
            action = "primary_accepted"
            reason = "Primary pypdf extraction passed the quality gate."
        elif (
            secondary is not None
            and secondary.quality.score
            >= primary.quality.score + self.minimum_secondary_improvement
        ):
            selected = secondary
            action = "secondary_selected"
            reason = (
                "Primary extraction did not pass; PyMuPDF improved the quality score "
                f"from {primary.quality.score:.4f} to {secondary.quality.score:.4f}."
            )
        else:
            selected = primary
            action = "primary_retained"
            reason = "Secondary extraction did not provide a material quality improvement."

        warnings = selected.quality.signals
        if selected.quality.status == "quarantined":
            action = "structured_fallback_required"
            warnings = (*warnings, "structured_fallback_required")
            reason += " The selected text remains quarantined pending structured fallback."
        candidates = (primary, secondary) if secondary is not None else (primary,)
        extraction = selected.extraction
        return PageParseResult(
            page_number=extraction.page_number,
            text=extraction.text,
            parser_name=extraction.parser_name,
            parser_version=extraction.parser_version,
            quality_score=selected.quality.score,
            quality_status=selected.quality.status,
            ocr_used=extraction.ocr_used,
            warnings=warnings,
            route_action=action,
            selection_reason=reason,
            candidates=candidates,
        )


class ParseQualityGateError(RuntimeError):
    """Raised when quarantined Router output is requested for chunking."""


def build_indexable_document(
    metadata: PaperMetadata,
    routed: DocumentParseResult,
) -> ParsedDocument:
    """Convert assessed pages for Chunking, rejecting every quarantined page."""

    quarantined = [
        page.page_number for page in routed.pages if page.quality_status == "quarantined"
    ]
    if quarantined:
        raise ParseQualityGateError(f"Quarantined pages cannot enter chunking: {quarantined}")
    if metadata.document_sha256 != routed.document_sha256:
        raise ParseQualityGateError("Routed document SHA-256 does not match metadata")
    if metadata.page_count != routed.page_count:
        raise ParseQualityGateError("Routed document page count does not match metadata")
    return ParsedDocument(
        metadata=metadata,
        pages=tuple(
            ParsedPage(
                page_number=page.page_number,
                text=page.text,
                parser_name=page.parser_name,
                parser_version=page.parser_version,
                parse_quality_score=page.quality_score,
                parse_quality_status=page.quality_status,
                ocr_used=page.ocr_used,
                parse_warnings=page.warnings,
            )
            for page in routed.pages
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
