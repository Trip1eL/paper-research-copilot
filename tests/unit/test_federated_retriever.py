from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.integrations import CachedEmbeddingProvider
from paper_research_copilot.retrieval import FederatedRrfRetriever


def _evidence(number: int, *, corpus_id: str) -> RetrievedChunk:
    text = f"Evidence {number} from {corpus_id}."
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=1 / number,
        chunk=PaperChunk(
            chunk_id=f"chunk-{number}",
            document_sha256="a" * 64,
            chunk_index=number,
            chunking_version="chunking_v1",
            corpus_id=corpus_id,
            paper_id=f"paper-{number}",
            title=f"Paper {number}",
            source_path=f"paper-{number}.pdf",
            page_number=1,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


class _Retriever:
    def __init__(self, ranking: tuple[RetrievedChunk, ...]) -> None:
        self.ranking = ranking
        self.requested_top_k: int | None = None

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.requested_top_k = top_k
        return self.ranking[:top_k]


class _Embeddings:
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def embed(self, texts) -> list[list[float]]:
        self.calls.append(tuple(texts))
        return [[float(len(text)), 0.0, 0.0] for text in texts]


def test_federated_rrf_fuses_sources_and_deduplicates_chunk_ids() -> None:
    curated = _Retriever((_evidence(1, corpus_id="curated"), _evidence(2, corpus_id="curated")))
    dynamic = _Retriever((_evidence(2, corpus_id="dynamic"), _evidence(3, corpus_id="dynamic")))
    retriever = FederatedRrfRetriever(
        {"dynamic": dynamic, "curated": curated},
        candidate_pool_per_source=3,
    )

    results = retriever.retrieve("agent evidence", top_k=3)

    assert retriever.source_names == ("curated", "dynamic")
    assert curated.requested_top_k == 3
    assert dynamic.requested_top_k == 3
    assert [item.chunk.chunk_id for item in results] == ["chunk-2", "chunk-1", "chunk-3"]
    assert [item.citation_id for item in results] == ["C1", "C2", "C3"]


def test_federated_rrf_tolerates_an_empty_dynamic_corpus() -> None:
    retriever = FederatedRrfRetriever(
        {
            "curated": _Retriever((_evidence(1, corpus_id="curated"),)),
            "dynamic": _Retriever(()),
        }
    )

    results = retriever.retrieve("agent evidence", top_k=2)

    assert [item.chunk.corpus_id for item in results] == ["curated"]


def test_embedding_cache_avoids_duplicate_federated_query_calls() -> None:
    provider = _Embeddings()
    cached = CachedEmbeddingProvider(provider, max_entries=2)

    first = cached.embed(["same query"])
    second = cached.embed(["same query"])

    assert first == second
    assert provider.calls == [("same query",)]


def test_embedding_cache_returns_batches_larger_than_its_capacity() -> None:
    provider = _Embeddings()
    cached = CachedEmbeddingProvider(provider, max_entries=1)

    vectors = cached.embed(["first query", "second query"])

    assert len(vectors) == 2
    assert provider.calls == [("first query", "second query")]
