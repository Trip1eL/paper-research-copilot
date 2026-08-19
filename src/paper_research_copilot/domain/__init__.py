"""Framework-independent models shared by the RAG pipeline."""

from paper_research_copilot.domain.answer import Answer
from paper_research_copilot.domain.corpus import (
    CorpusCatalog,
    CorpusManifestRecord,
    CorpusPaperAsset,
    CorpusPaperSpec,
    CorpusSpec,
)
from paper_research_copilot.domain.evidence import Citation, RetrievedChunk
from paper_research_copilot.domain.paper import (
    ChunkContext,
    IngestionSummary,
    PaperChunk,
    PaperMetadata,
    ParsedDocument,
    ParsedPage,
)
from paper_research_copilot.domain.parse import (
    DocumentParseResult,
    PageParseCandidate,
    PageParseResult,
    PageQualityFeatures,
    PageQualityResult,
    PageTextExtraction,
    ParseQualityStatus,
    ParserName,
    ParseRouteAction,
)

__all__ = [
    "Answer",
    "Citation",
    "ChunkContext",
    "CorpusCatalog",
    "CorpusManifestRecord",
    "CorpusPaperAsset",
    "CorpusPaperSpec",
    "CorpusSpec",
    "IngestionSummary",
    "DocumentParseResult",
    "PageParseCandidate",
    "PageParseResult",
    "PageQualityFeatures",
    "PageQualityResult",
    "PageTextExtraction",
    "PaperChunk",
    "PaperMetadata",
    "ParsedDocument",
    "ParsedPage",
    "ParseQualityStatus",
    "ParseRouteAction",
    "ParserName",
    "RetrievedChunk",
]
