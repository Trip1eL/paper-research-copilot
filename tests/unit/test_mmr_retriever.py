from collections.abc import Sequence

import pytest

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval import MmrDenseRetriever, VectorSearchResult


def _candidate(
    citation_number: int,
    *,
    score: float,
    vector: tuple[float, ...],
) -> VectorSearchResult:
    return VectorSearchResult(
        evidence=RetrievedChunk(
            citation_id=f"C{citation_number}",
            score=score,
            chunk=PaperChunk(
                chunk_id=f"chunk-{citation_number}",
                document_sha256="a" * 64,
                chunk_index=citation_number - 1,
                chunking_version="chunking_v1",
                paper_id=f"paper-{citation_number}",
                title=f"Paper {citation_number}",
                source_path=f"paper-{citation_number}.pdf",
                page_number=1,
                char_start=0,
                char_end=10,
                text="agent text",
            ),
        ),
        vector=vector,
    )


class _FakeEmbeddings:
    dimension = 2

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        assert list(texts) == ["question"]
        return [[1.0, 0.0]]


class _FakeVectorStore:
    def __init__(self, candidates: tuple[VectorSearchResult, ...]) -> None:
        self.candidates = candidates
        self.requested_limit: int | None = None

    def search_with_vectors(
        self,
        query_vector: Sequence[float],
        limit: int,
    ) -> tuple[VectorSearchResult, ...]:
        assert list(query_vector) == [1.0, 0.0]
        self.requested_limit = limit
        return self.candidates[:limit]


def _candidates() -> tuple[VectorSearchResult, ...]:
    return (
        _candidate(1, score=0.99, vector=(1.0, 0.0)),
        _candidate(2, score=0.98, vector=(0.999, 0.001)),
        _candidate(3, score=0.80, vector=(0.0, 1.0)),
    )


def test_low_lambda_prefers_semantic_novelty() -> None:
    store = _FakeVectorStore(_candidates())
    retriever = MmrDenseRetriever(
        _FakeEmbeddings(),
        store,
        candidate_pool_size=3,
        lambda_mult=0.5,
    )

    results = retriever.retrieve("question", top_k=2)

    assert store.requested_limit == 3
    assert [item.chunk.chunk_id for item in results] == ["chunk-1", "chunk-3"]
    assert [item.citation_id for item in results] == ["C1", "C2"]


def test_high_lambda_prefers_dense_relevance() -> None:
    retriever = MmrDenseRetriever(
        _FakeEmbeddings(),
        _FakeVectorStore(_candidates()),
        candidate_pool_size=3,
        lambda_mult=0.95,
    )

    results = retriever.retrieve("question", top_k=2)

    assert [item.chunk.chunk_id for item in results] == ["chunk-1", "chunk-2"]


@pytest.mark.parametrize("lambda_mult", [-0.1, 1.1])
def test_mmr_rejects_lambda_outside_unit_interval(lambda_mult: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        MmrDenseRetriever(
            _FakeEmbeddings(),
            _FakeVectorStore(_candidates()),
            lambda_mult=lambda_mult,
        )
