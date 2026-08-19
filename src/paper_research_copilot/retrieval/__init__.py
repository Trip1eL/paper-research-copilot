"""Evidence retrieval components."""

from paper_research_copilot.retrieval.coverage import (
    QUERY_DECOMPOSITION_PROMPT_VERSION,
    CachedQueryDecomposer,
    CoverageAwareRetriever,
    CoverageTrace,
    QueryDecompositionRecord,
    coverage_round_robin,
    find_decomposition_alias_leaks,
)
from paper_research_copilot.retrieval.factory import RetrievalMode, RetrieverFactory
from paper_research_copilot.retrieval.hybrid import (
    HybridMmrRetriever,
    RrfFusionRetriever,
    fuse_query_rankings_max,
    fuse_rankings,
)
from paper_research_copilot.retrieval.lexical import Bm25Retriever
from paper_research_copilot.retrieval.query_rewrite import (
    QUERY_REWRITE_PROMPT_VERSION,
    CachedQueryRewriter,
    MultiQueryRrfRetriever,
    QueryRewriteRecord,
    find_query_rewrite_alias_leaks,
)
from paper_research_copilot.retrieval.reranker import (
    RerankCandidateTrace,
    RerankingRetriever,
    RerankTrace,
)
from paper_research_copilot.retrieval.retriever import (
    CandidateRetriever,
    DenseRetriever,
    DiversifiedDenseRetriever,
    MmrDenseRetriever,
)
from paper_research_copilot.retrieval.vector_store import QdrantVectorStore, VectorSearchResult

__all__ = [
    "DenseRetriever",
    "DiversifiedDenseRetriever",
    "Bm25Retriever",
    "CandidateRetriever",
    "HybridMmrRetriever",
    "MmrDenseRetriever",
    "CachedQueryRewriter",
    "CachedQueryDecomposer",
    "CoverageAwareRetriever",
    "CoverageTrace",
    "MultiQueryRrfRetriever",
    "QUERY_REWRITE_PROMPT_VERSION",
    "QUERY_DECOMPOSITION_PROMPT_VERSION",
    "QueryDecompositionRecord",
    "QueryRewriteRecord",
    "find_query_rewrite_alias_leaks",
    "find_decomposition_alias_leaks",
    "coverage_round_robin",
    "fuse_rankings",
    "fuse_query_rankings_max",
    "QdrantVectorStore",
    "RetrievalMode",
    "RetrieverFactory",
    "RrfFusionRetriever",
    "RerankCandidateTrace",
    "RerankingRetriever",
    "RerankTrace",
    "VectorSearchResult",
]
