"""Runtime selection and lifecycle management for production retrievers."""

from collections.abc import Callable, Hashable, Sequence
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
        generation_loader: Callable[[], Hashable] | None = None,
        allow_empty_discovery: bool = False,
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
        self._generation_loader = generation_loader
        self._allow_empty_discovery = allow_empty_discovery
        self._hybrid_retriever: CandidateRetriever | None = None
        self._hybrid_generation: Hashable | None = None

    def get(self, mode: RetrievalMode | str) -> CandidateRetriever:
        retrieval_mode = RetrievalMode(mode)
        if retrieval_mode is RetrievalMode.EVIDENCE:
            return self._dense_retriever
        generation = self._generation_loader() if self._generation_loader else None
        if self._hybrid_retriever is None or generation != self._hybrid_generation:
            chunks = tuple(self._chunk_loader())
            if not chunks:
                if self._allow_empty_discovery:
                    self._hybrid_retriever = self._dense_retriever
                    self._hybrid_generation = generation
                    return self._hybrid_retriever
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
            self._hybrid_generation = generation
        return self._hybrid_retriever

    def retrieve(
        self,
        question: str,
        top_k: int,
        mode: RetrievalMode | str,
    ) -> tuple[RetrievedChunk, ...]:
        return self.get(mode).retrieve(question, top_k)
