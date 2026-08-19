"""Paper parsing and page-aware chunking."""

from paper_research_copilot.ingestion.chunker import CHUNKING_VERSION, PageAwareChunker
from paper_research_copilot.ingestion.corpus import (
    CorpusCatalogLoader,
    CorpusPreparer,
    CorpusValidationError,
    PreparedCorpus,
    PreparedPaper,
)
from paper_research_copilot.ingestion.extractors import (
    PdfExtractionError,
    PdfTextExtractor,
    PyMuPdfExtractor,
    PypdfExtractor,
    normalize_pdf_text,
)
from paper_research_copilot.ingestion.parser import PdfParser, PdfParsingError
from paper_research_copilot.ingestion.quality import (
    PageQualityScorer,
    calculate_page_quality_features,
)
from paper_research_copilot.ingestion.router import (
    FastParserRouter,
    ParseQualityGateError,
    build_indexable_document,
)
from paper_research_copilot.ingestion.statistics import (
    CorpusChunkStatistics,
    calculate_chunk_statistics,
    write_chunk_statistics,
)

__all__ = [
    "CHUNKING_VERSION",
    "CorpusCatalogLoader",
    "CorpusChunkStatistics",
    "CorpusPreparer",
    "CorpusValidationError",
    "FastParserRouter",
    "PageAwareChunker",
    "PageQualityScorer",
    "ParseQualityGateError",
    "PdfExtractionError",
    "PdfParser",
    "PdfParsingError",
    "PdfTextExtractor",
    "PreparedCorpus",
    "PreparedPaper",
    "PyMuPdfExtractor",
    "PypdfExtractor",
    "build_indexable_document",
    "calculate_chunk_statistics",
    "calculate_page_quality_features",
    "normalize_pdf_text",
    "write_chunk_statistics",
]
