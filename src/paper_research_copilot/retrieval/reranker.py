"""Candidate reranking with observable rank and score changes."""

import time
from dataclasses import dataclass

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.integrations import RerankerProvider
from paper_research_copilot.retrieval.retriever import CandidateRetriever


@dataclass(frozen=True)
class RerankCandidateTrace:
    chunk_id: str
    paper_id: str | None
    page_number: int
    original_rank: int
    original_score: float
    reranker_score: float
    reranked_rank: int


@dataclass(frozen=True)
class RerankTrace:
    model: str
    candidate_count: int
    latency_ms: float
    candidates: tuple[RerankCandidateTrace, ...]


class RerankingRetriever:
    def __init__(
        self,
        candidate_retriever: CandidateRetriever,
        reranker: RerankerProvider,
        *,
        candidate_pool_size: int = 50,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        self._candidate_retriever = candidate_retriever
        self._reranker = reranker
        self.candidate_pool_size = candidate_pool_size
        self._traces: dict[str, RerankTrace] = {}

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        candidates = self._candidate_retriever.retrieve(
            question,
            max(top_k, self.candidate_pool_size),
        )
        if not candidates:
            return ()
        started = time.perf_counter()
        scores = self._reranker.score(
            question,
            [candidate.chunk.text for candidate in candidates],
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        scored = sorted(
            enumerate(zip(candidates, scores, strict=True), start=1),
            key=lambda item: (-item[1][1], item[0], item[1][0].chunk.chunk_id),
        )
        reranked = tuple(
            candidate.model_copy(update={"citation_id": f"C{rank}", "score": reranker_score})
            for rank, (_, (candidate, reranker_score)) in enumerate(scored, start=1)
        )
        reranked_positions = {
            candidate.chunk.chunk_id: rank for rank, candidate in enumerate(reranked, start=1)
        }
        self._traces[question] = RerankTrace(
            model=self._reranker.model,
            candidate_count=len(candidates),
            latency_ms=latency_ms,
            candidates=tuple(
                RerankCandidateTrace(
                    chunk_id=candidate.chunk.chunk_id,
                    paper_id=candidate.chunk.paper_id,
                    page_number=candidate.chunk.page_number,
                    original_rank=original_rank,
                    original_score=candidate.score,
                    reranker_score=reranker_score,
                    reranked_rank=reranked_positions[candidate.chunk.chunk_id],
                )
                for original_rank, (candidate, reranker_score) in enumerate(
                    zip(candidates, scores, strict=True),
                    start=1,
                )
            ),
        )
        return reranked[:top_k]

    def trace_for(self, question: str) -> RerankTrace:
        try:
            return self._traces[question]
        except KeyError as exc:
            raise LookupError("Question has not been reranked") from exc
