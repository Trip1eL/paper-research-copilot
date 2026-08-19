"""Academic search provider adapters."""

from paper_research_copilot.integrations.scholarly.arxiv import (
    ARXIV_API_URL,
    ArxivSearchError,
    ArxivSearchProvider,
)
from paper_research_copilot.integrations.scholarly.base import (
    AcademicSearchProvider,
    rank_and_deduplicate_candidates,
)
from paper_research_copilot.integrations.scholarly.downloader import (
    ARXIV_HOSTS,
    BoundedPaperDownloader,
    DownloadValidationError,
)

__all__ = [
    "ARXIV_API_URL",
    "AcademicSearchProvider",
    "ARXIV_HOSTS",
    "ArxivSearchError",
    "ArxivSearchProvider",
    "BoundedPaperDownloader",
    "DownloadValidationError",
    "rank_and_deduplicate_candidates",
]
