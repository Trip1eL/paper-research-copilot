"""Dense evidence retrieval services."""

from collections import Counter
from collections.abc import Sequence
from typing import Protocol

import numpy as np

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.integrations import EmbeddingProvider
from paper_research_copilot.retrieval.vector_store import QdrantVectorStore, VectorSearchResult


class CandidateRetriever(Protocol):
    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]: ...


class VectorCandidateStore(Protocol):
    def search_with_vectors(
        self,
        query_vector: Sequence[float],
        limit: int,
    ) -> tuple[VectorSearchResult, ...]: ...


class CandidateVectorLookup(Protocol):
    def get_vectors(self, chunk_ids: Sequence[str]) -> dict[str, tuple[float, ...]]: ...


class DenseRetriever:
    def __init__(self, embeddings: EmbeddingProvider, vector_store: QdrantVectorStore) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        query_vector = self._embeddings.embed([question])[0]
        return self._vector_store.search(query_vector, limit=top_k)


class DiversifiedDenseRetriever:
    """Apply deterministic paper/page constraints to a larger dense candidate pool."""

    def __init__(
        self,
        dense_retriever: CandidateRetriever,
        *,
        candidate_pool_size: int = 50,
        max_chunks_per_paper: int = 3,
        max_chunks_per_page: int = 1,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if max_chunks_per_paper < 1:
            raise ValueError("Max chunks per paper must be at least 1")
        if max_chunks_per_page < 1:
            raise ValueError("Max chunks per page must be at least 1")
        if max_chunks_per_page > max_chunks_per_paper:
            raise ValueError("Max chunks per page cannot exceed max chunks per paper")
        self._dense_retriever = dense_retriever
        self.candidate_pool_size = candidate_pool_size
        self.max_chunks_per_paper = max_chunks_per_paper
        self.max_chunks_per_page = max_chunks_per_page

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        candidates = self._dense_retriever.retrieve(
            question,
            max(top_k, self.candidate_pool_size),
        )
        paper_counts: Counter[str] = Counter()
        page_counts: Counter[tuple[str, int]] = Counter()
        selected: list[RetrievedChunk] = []

        for candidate in candidates:
            chunk = candidate.chunk
            paper_key = chunk.paper_id or chunk.source_path
            page_key = (paper_key, chunk.page_number)
            if paper_counts[paper_key] >= self.max_chunks_per_paper:
                continue
            if page_counts[page_key] >= self.max_chunks_per_page:
                continue
            selected.append(candidate.model_copy(update={"citation_id": f"C{len(selected) + 1}"}))
            paper_counts[paper_key] += 1
            page_counts[page_key] += 1
            if len(selected) == top_k:
                break

        return tuple(selected)


class MmrDenseRetriever:
    """Select dense candidates by balancing query relevance and semantic novelty."""

    def __init__(
        self,
        embeddings: EmbeddingProvider,
        vector_store: VectorCandidateStore,
        *,
        candidate_pool_size: int = 50,
        lambda_mult: float = 0.85,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if not 0 <= lambda_mult <= 1:
            raise ValueError("MMR lambda must be between 0 and 1")
        self._embeddings = embeddings
        self._vector_store = vector_store
        self.candidate_pool_size = candidate_pool_size
        self.lambda_mult = lambda_mult

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        query_vector = self._embeddings.embed([question])[0]
        remaining = list(
            self._vector_store.search_with_vectors(
                query_vector,
                limit=max(top_k, self.candidate_pool_size),
            )
        )
        selected = select_mmr(
            remaining,
            [candidate.evidence.score for candidate in remaining],
            top_k=top_k,
            lambda_mult=self.lambda_mult,
        )

        return tuple(
            candidate.evidence.model_copy(update={"citation_id": f"C{index}"})
            for index, candidate in enumerate(selected, start=1)
        )


def select_mmr(
    candidates: Sequence[VectorSearchResult],
    relevance_scores: Sequence[float],
    *,
    top_k: int,
    lambda_mult: float,
) -> list[VectorSearchResult]:
    if len(candidates) != len(relevance_scores):
        raise ValueError("MMR candidates and relevance scores must have the same length")
    if not candidates:
        return []
    vectors = np.asarray([candidate.vector for candidate in candidates], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1)
    normalized = np.zeros_like(vectors)
    nonzero = norms > 0
    normalized[nonzero] = vectors[nonzero] / norms[nonzero, np.newaxis]
    relevance = np.asarray(relevance_scores, dtype=np.float32)

    selected_indices = [0]
    available = np.ones(len(candidates), dtype=np.bool_)
    available[0] = False
    while available.any() and len(selected_indices) < top_k:
        remaining_indices = np.flatnonzero(available)
        similarities = normalized[remaining_indices] @ normalized[selected_indices].T
        redundancy = np.max(similarities, axis=1)
        mmr_scores = lambda_mult * relevance[remaining_indices] - (1 - lambda_mult) * redundancy
        best_index = int(remaining_indices[int(np.argmax(mmr_scores))])
        selected_indices.append(best_index)
        available[best_index] = False

    return [candidates[index] for index in selected_indices]
