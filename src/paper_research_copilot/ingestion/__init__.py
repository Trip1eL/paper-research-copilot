"""Paper parsing and page-aware chunking."""

from paper_research_copilot.ingestion.chunker import CHUNKING_VERSION, PageAwareChunker
from paper_research_copilot.ingestion.corpus import (
    CorpusCatalogLoader,
    CorpusPreparer,
    CorpusValidationError,
    PreparedCorpus,
    PreparedPaper,
)
from paper_research_copilot.ingestion.parser import PdfParser, PdfParsingError
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
    "PageAwareChunker",
    "PdfParser",
    "PdfParsingError",
    "PreparedCorpus",
    "PreparedPaper",
    "calculate_chunk_statistics",
    "write_chunk_statistics",
]
