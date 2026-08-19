"""Runtime selection and lifecycle management for production retrievers."""

from collections.abc import Callable, Sequence
from enum import StrEnum

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval.hybrid import RrfFusionRetriever
from paper_research_copilot.retrieval.lexical import Bm25Retriever
from paper_research_copilot.retrieval.retriever import CandidateRetriever


class RetrievalMode(StrEnum):
    """User-visible retrieval intent."""

    EVIDENCE = "evidence"
    DISCOVERY = "discovery"


class RetrieverFactory:
    """Build each mode's retriever once and reuse it for the runtime lifetime."""

    def __init__(
        self,
        dense_retriever: CandidateRetriever,
        chunk_loader: Callable[[], Sequence[PaperChunk]],
        *,
        candidate_pool_size: int = 50,
        rrf_k: int = 60,
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if rrf_k < 1:
            raise ValueError("RRF k must be at least 1")
        self._dense_retriever = dense_retriever
        self._chunk_loader = chunk_loader
        self._candidate_pool_size = candidate_pool_size
        self._rrf_k = rrf_k
        self._bm25_k1 = bm25_k1
        self._bm25_b = bm25_b
        self._hybrid_retriever: CandidateRetriever | None = None

    def get(self, mode: RetrievalMode | str) -> CandidateRetriever:
        retrieval_mode = RetrievalMode(mode)
        if retrieval_mode is RetrievalMode.EVIDENCE:
            return self._dense_retriever
        if self._hybrid_retriever is None:
            chunks = tuple(self._chunk_loader())
            if not chunks:
                raise LookupError("Cannot build Hybrid RRF: the Qdrant collection is empty")
            lexical_retriever = Bm25Retriever(
                chunks,
                k1=self._bm25_k1,
                b=self._bm25_b,
            )
            self._hybrid_retriever = RrfFusionRetriever(
                self._dense_retriever,
                lexical_retriever,
                candidate_pool_size=self._candidate_pool_size,
                rrf_k=self._rrf_k,
            )
        return self._hybrid_retriever

    def retrieve(
        self,
        question: str,
        top_k: int,
        mode: RetrievalMode | str,
    ) -> tuple[RetrievedChunk, ...]:
        return self.get(mode).retrieve(question, top_k)
