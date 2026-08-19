from collections.abc import Sequence

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval import (
    Bm25Retriever,
    HybridMmrRetriever,
    MultiQueryRrfRetriever,
    RrfFusionRetriever,
    fuse_query_rankings_max,
    fuse_rankings,
)


def _chunk(number: int, text: str) -> PaperChunk:
    return PaperChunk(
        chunk_id=f"chunk-{number}",
        document_sha256="a" * 64,
        chunk_index=number,
        chunking_version="chunking_v1",
        paper_id=f"paper-{number}",
        title=f"Paper {number}",
        source_path=f"paper-{number}.pdf",
        page_number=1,
        char_start=0,
        char_end=len(text),
        text=text,
    )


def _evidence(number: int, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=score,
        chunk=_chunk(number, f"evidence {number}"),
    )


class _FakeRetriever:
    def __init__(self, evidence: tuple[RetrievedChunk, ...]) -> None:
        self.evidence = evidence
        self.requested_top_k: int | None = None

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.requested_top_k = top_k
        return self.evidence[:top_k]


class _FakeVectorLookup:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors

    def get_vectors(self, chunk_ids: Sequence[str]) -> dict[str, tuple[float, ...]]:
        return {chunk_id: self.vectors[chunk_id] for chunk_id in chunk_ids}


class _FakeQueryRewriter:
    def rewrite(self, question: str) -> tuple[str, ...]:
        assert question == "原始问题"
        return ("english mechanism", "contrasting method")


def test_bm25_ranks_stemmed_english_terms_and_filters_zero_scores() -> None:
    retriever = Bm25Retriever(
        (
            _chunk(1, "Language agents use reasoning and external tools."),
            _chunk(2, "Image classification with convolutional networks."),
        )
    )

    results = retriever.retrieve("reasoning with tools", top_k=2)
    chinese_only_results = retriever.retrieve("如何改进智能体？", top_k=2)

    assert [item.chunk.chunk_id for item in results] == ["chunk-1"]
    assert results[0].score > 0
    assert chinese_only_results == ()


def test_rrf_promotes_chunks_found_by_both_retrievers() -> None:
    dense = _FakeRetriever((_evidence(1, 0.9), _evidence(2, 0.8)))
    lexical = _FakeRetriever((_evidence(2, 3.0), _evidence(3, 2.0)))
    retriever = RrfFusionRetriever(
        dense,
        lexical,
        candidate_pool_size=3,
        rrf_k=60,
    )

    results = retriever.retrieve("question", top_k=3)

    assert dense.requested_top_k == 3
    assert lexical.requested_top_k == 3
    assert [item.chunk.chunk_id for item in results] == ["chunk-2", "chunk-1", "chunk-3"]
    assert [item.citation_id for item in results] == ["C1", "C2", "C3"]


def test_hybrid_mmr_uses_normalized_rrf_scores_and_candidate_vectors() -> None:
    fusion = _FakeRetriever(
        (
            _evidence(1, 0.030),
            _evidence(2, 0.029),
            _evidence(3, 0.020),
        )
    )
    vectors = _FakeVectorLookup(
        {
            "chunk-1": (1.0, 0.0),
            "chunk-2": (0.999, 0.001),
            "chunk-3": (0.0, 1.0),
        }
    )
    retriever = HybridMmrRetriever(
        fusion,
        vectors,
        candidate_pool_size=3,
        lambda_mult=0.5,
    )

    results = retriever.retrieve("question", top_k=2)

    assert fusion.requested_top_k == 3
    assert [item.chunk.chunk_id for item in results] == ["chunk-1", "chunk-3"]
    assert [item.citation_id for item in results] == ["C1", "C2"]


def test_multi_query_rrf_fuses_original_and_rewritten_rankings() -> None:
    dense = _FakeRetriever((_evidence(1, 0.9), _evidence(2, 0.8)))
    lexical = _FakeRetriever((_evidence(2, 3.0), _evidence(3, 2.0)))
    retriever = MultiQueryRrfRetriever(  # type: ignore[arg-type]
        dense,
        lexical,
        _FakeQueryRewriter(),
        candidate_pool_size=3,
        rrf_k=60,
    )

    results = retriever.retrieve("原始问题", top_k=3)

    assert retriever.queries_for("原始问题") == (
        "原始问题",
        "english mechanism",
        "contrasting method",
    )
    assert [item.chunk.chunk_id for item in results] == ["chunk-2", "chunk-1", "chunk-3"]


def test_weighted_rrf_can_balance_original_query_against_rewrite_group() -> None:
    original = (_evidence(2, 1.0),)
    rewrites = tuple((_evidence(1, 1.0),) for _ in range(3))

    flat = fuse_rankings((original, *rewrites), top_k=2, rrf_k=60)
    weighted = fuse_rankings(
        (original, *rewrites),
        top_k=2,
        rrf_k=60,
        ranking_weights=(0.6, 0.4 / 3, 0.4 / 3, 0.4 / 3),
    )

    assert [item.chunk.chunk_id for item in flat] == ["chunk-1", "chunk-2"]
    assert [item.chunk.chunk_id for item in weighted] == ["chunk-2", "chunk-1"]


def test_max_over_query_does_not_accumulate_repeated_query_hits() -> None:
    specialized = (_evidence(2, 1.0),)
    query_rankings = (
        ((), (_evidence(3, 1.0), _evidence(1, 0.9))),
        ((), (_evidence(4, 1.0), _evidence(1, 0.9))),
        (specialized, ()),
    )

    results = fuse_query_rankings_max(query_rankings, top_k=3, rrf_k=60)

    assert results[0].chunk.chunk_id == "chunk-2"
