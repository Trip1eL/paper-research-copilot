from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval import (
    RetrievalMode,
    RetrieverFactory,
    RrfFusionRetriever,
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


class _DenseRetriever:
    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return (
            RetrievedChunk(
                citation_id="C1",
                score=0.9,
                chunk=_chunk(1, "Agents use semantic reasoning."),
            ),
        )


def test_factory_maps_modes_and_builds_hybrid_only_once() -> None:
    dense = _DenseRetriever()
    load_count = 0

    def load_chunks() -> tuple[PaperChunk, ...]:
        nonlocal load_count
        load_count += 1
        return (
            _chunk(1, "Agents use semantic reasoning."),
            _chunk(2, "External tools provide observations."),
        )

    factory = RetrieverFactory(dense, load_chunks)

    evidence_retriever = factory.get(RetrievalMode.EVIDENCE)
    first_discovery_retriever = factory.get(RetrievalMode.DISCOVERY)
    second_discovery_retriever = factory.get("discovery")

    assert evidence_retriever is dense
    assert isinstance(first_discovery_retriever, RrfFusionRetriever)
    assert second_discovery_retriever is first_discovery_retriever
    assert load_count == 1


def test_factory_does_not_load_bm25_corpus_for_evidence_mode() -> None:
    dense = _DenseRetriever()

    def fail_if_loaded() -> tuple[PaperChunk, ...]:
        raise AssertionError("Evidence mode must not build the BM25 index")

    factory = RetrieverFactory(dense, fail_if_loaded)

    results = factory.retrieve("How do agents reason?", 1, RetrievalMode.EVIDENCE)

    assert results[0].chunk.chunk_id == "chunk-1"
