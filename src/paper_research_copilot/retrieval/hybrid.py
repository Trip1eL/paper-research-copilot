"""Rank fusion and MMR selection for hybrid retrieval."""

from collections import defaultdict
from collections.abc import Sequence

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.retrieval.retriever import (
    CandidateRetriever,
    CandidateVectorLookup,
    select_mmr,
)
from paper_research_copilot.retrieval.vector_store import VectorSearchResult


class RrfFusionRetriever:
    """Fuse dense and lexical rankings with Reciprocal Rank Fusion."""

    def __init__(
        self,
        dense_retriever: CandidateRetriever,
        lexical_retriever: CandidateRetriever,
        *,
        candidate_pool_size: int = 50,
        rrf_k: int = 60,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if rrf_k < 1:
            raise ValueError("RRF k must be at least 1")
        self._dense_retriever = dense_retriever
        self._lexical_retriever = lexical_retriever
        self.candidate_pool_size = candidate_pool_size
        self.rrf_k = rrf_k

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        pool_size = max(top_k, self.candidate_pool_size)
        rankings = (
            self._dense_retriever.retrieve(question, pool_size),
            self._lexical_retriever.retrieve(question, pool_size),
        )
        return fuse_rankings(rankings, top_k=top_k, rrf_k=self.rrf_k)


def fuse_rankings(
    rankings: Sequence[Sequence[RetrievedChunk]],
    *,
    top_k: int,
    rrf_k: int,
    ranking_weights: Sequence[float] | None = None,
) -> tuple[RetrievedChunk, ...]:
    """Fuse any number of ranked lists with deterministic Reciprocal Rank Fusion."""

    if top_k < 1:
        raise ValueError("Top-K must be at least 1")
    if rrf_k < 1:
        raise ValueError("RRF k must be at least 1")
    weights = tuple(ranking_weights or (1.0 for _ in rankings))
    if len(weights) != len(rankings):
        raise ValueError("RRF rankings and weights must have the same length")
    if any(weight < 0 for weight in weights) or not any(weight > 0 for weight in weights):
        raise ValueError("RRF weights must be non-negative with at least one positive value")
    scores: defaultdict[str, float] = defaultdict(float)
    candidates: dict[str, RetrievedChunk] = {}
    best_ranks: dict[str, int] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, item in enumerate(ranking, start=1):
            chunk_id = item.chunk.chunk_id
            scores[chunk_id] += weight / (rrf_k + rank)
            candidates.setdefault(chunk_id, item)
            best_ranks[chunk_id] = min(best_ranks.get(chunk_id, rank), rank)

    return _rank_fused_candidates(scores, candidates, best_ranks, top_k)


def fuse_query_rankings_max(
    query_rankings: Sequence[Sequence[Sequence[RetrievedChunk]]],
    *,
    top_k: int,
    rrf_k: int,
) -> tuple[RetrievedChunk, ...]:
    """Use each candidate's best per-query RRF score instead of summing across queries."""

    if top_k < 1:
        raise ValueError("Top-K must be at least 1")
    if rrf_k < 1:
        raise ValueError("RRF k must be at least 1")
    scores: dict[str, float] = {}
    candidates: dict[str, RetrievedChunk] = {}
    best_ranks: dict[str, int] = {}
    for rankings in query_rankings:
        query_scores: defaultdict[str, float] = defaultdict(float)
        for ranking in rankings:
            for rank, item in enumerate(ranking, start=1):
                chunk_id = item.chunk.chunk_id
                query_scores[chunk_id] += 1 / (rrf_k + rank)
                candidates.setdefault(chunk_id, item)
                best_ranks[chunk_id] = min(best_ranks.get(chunk_id, rank), rank)
        for chunk_id, score in query_scores.items():
            scores[chunk_id] = max(scores.get(chunk_id, 0.0), score)

    return _rank_fused_candidates(scores, candidates, best_ranks, top_k)


def _rank_fused_candidates(
    scores: dict[str, float],
    candidates: dict[str, RetrievedChunk],
    best_ranks: dict[str, int],
    top_k: int,
) -> tuple[RetrievedChunk, ...]:

    ordered_ids = sorted(
        candidates,
        key=lambda chunk_id: (-scores[chunk_id], best_ranks[chunk_id], chunk_id),
    )
    return tuple(
        candidates[chunk_id].model_copy(
            update={"citation_id": f"C{rank}", "score": scores[chunk_id]}
        )
        for rank, chunk_id in enumerate(ordered_ids[:top_k], start=1)
    )


class HybridMmrRetriever:
    """Apply MMR to a normalized RRF candidate ranking."""

    def __init__(
        self,
        fusion_retriever: CandidateRetriever,
        vector_lookup: CandidateVectorLookup,
        *,
        candidate_pool_size: int = 50,
        lambda_mult: float = 0.85,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if not 0 <= lambda_mult <= 1:
            raise ValueError("MMR lambda must be between 0 and 1")
        self._fusion_retriever = fusion_retriever
        self._vector_lookup = vector_lookup
        self.candidate_pool_size = candidate_pool_size
        self.lambda_mult = lambda_mult

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        evidence = self._fusion_retriever.retrieve(
            question,
            max(top_k, self.candidate_pool_size),
        )
        vectors = self._vector_lookup.get_vectors([item.chunk.chunk_id for item in evidence])
        candidates = [
            VectorSearchResult(evidence=item, vector=vectors[item.chunk.chunk_id])
            for item in evidence
            if item.chunk.chunk_id in vectors
        ]
        relevance = _min_max_scores([item.evidence.score for item in candidates])
        selected = select_mmr(
            candidates,
            relevance,
            top_k=top_k,
            lambda_mult=self.lambda_mult,
        )
        return tuple(
            candidate.evidence.model_copy(update={"citation_id": f"C{rank}"})
            for rank, candidate in enumerate(selected, start=1)
        )


def _min_max_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lowest = min(scores)
    highest = max(scores)
    if highest == lowest:
        return [1.0 for _ in scores]
    return [(score - lowest) / (highest - lowest) for score in scores]
