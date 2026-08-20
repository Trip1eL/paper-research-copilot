"""Deterministic retrieval across immutable and dynamically acquired corpora."""

from collections.abc import Mapping

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.retrieval.factory import RetrievalMode, RetrieverFactory
from paper_research_copilot.retrieval.hybrid import fuse_rankings
from paper_research_copilot.retrieval.retriever import CandidateRetriever


class FederatedRrfRetriever:
    """Retrieve from each corpus independently, then fuse their rankings with RRF."""

    def __init__(
        self,
        sources: Mapping[str, CandidateRetriever],
        *,
        candidate_pool_per_source: int = 50,
        rrf_k: int = 60,
    ) -> None:
        if not sources:
            raise ValueError("Federated retrieval requires at least one source")
        if any(not name.strip() for name in sources):
            raise ValueError("Federated source names must not be empty")
        if candidate_pool_per_source < 1:
            raise ValueError("Candidate pool per source must be at least one")
        if rrf_k < 1:
            raise ValueError("RRF k must be at least one")
        self._sources = tuple(sorted(sources.items()))
        self.candidate_pool_per_source = candidate_pool_per_source
        self.rrf_k = rrf_k

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._sources)

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if top_k < 1:
            raise ValueError("Top-K must be at least one")
        pool_size = max(top_k, self.candidate_pool_per_source)
        rankings = tuple(
            retriever.retrieve(question, pool_size)
            for _, retriever in self._sources
        )
        return fuse_rankings(rankings, top_k=top_k, rrf_k=self.rrf_k)


class FactoryBackedRetriever:
    """Resolve the selected mode on every call so mutable BM25 generations can refresh."""

    def __init__(
        self,
        factory: RetrieverFactory,
        mode: RetrievalMode | str,
    ) -> None:
        self._factory = factory
        self._mode = mode

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self._factory.retrieve(question, top_k, self._mode)
