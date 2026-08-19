from pathlib import Path

import pytest

from paper_research_copilot.domain import PaperChunk
from paper_research_copilot.retrieval import QdrantVectorStore


def _chunk(chunk_id: str, text: str, index: int) -> PaperChunk:
    return PaperChunk(
        chunk_id=chunk_id,
        document_sha256="a" * 64,
        chunk_index=index,
        chunking_version="chunking_v1",
        paper_id="arxiv:0000.00000",
        title="Agent Paper",
        source_path="agent.pdf",
        page_number=1,
        char_start=index * 20,
        char_end=index * 20 + len(text),
        text=text,
    )


def test_qdrant_local_upsert_and_search(tmp_path: Path) -> None:
    store = QdrantVectorStore(
        collection_name="test_chunks",
        dimension=3,
        path=tmp_path / "qdrant",
    )
    try:
        chunks = (
            _chunk("89dc7b16-6840-50ef-9850-e1a521ca24ac", "tool use", 0),
            _chunk("e76c1f93-3e52-5bb4-8d4d-a7d2d5844f79", "image classification", 1),
        )
        store.upsert(chunks, ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]))

        results = store.search([0.9, 0.1, 0.0], limit=2)
        vector_results = store.search_with_vectors([0.9, 0.1, 0.0], limit=2)
        listed_chunks = store.list_chunks(page_size=1)
        vectors = store.get_vectors([chunk.chunk_id for chunk in chunks])

        assert results[0].chunk.text == "tool use"
        assert results[0].citation_id == "C1"
        assert results[0].score == pytest.approx(0.99388, rel=1e-4)
        assert vector_results[0].evidence.chunk.text == "tool use"
        assert vector_results[0].vector == (1.0, 0.0, 0.0)
        assert [chunk.chunk_id for chunk in listed_chunks] == sorted(
            chunk.chunk_id for chunk in chunks
        )
        assert vectors[chunks[0].chunk_id] == (1.0, 0.0, 0.0)
        assert vectors[chunks[1].chunk_id] == (0.0, 1.0, 0.0)
        assert store.count() == 2
    finally:
        store.close()


def test_qdrant_replace_by_metadata_removes_stale_chunks(tmp_path: Path) -> None:
    store = QdrantVectorStore(
        collection_name="test_replace",
        dimension=3,
        path=tmp_path / "qdrant",
    )
    metadata = {
        "paper_id": "arxiv:0000.00000",
        "chunking_version": "chunking_v1",
    }
    try:
        initial = (
            _chunk("89dc7b16-6840-50ef-9850-e1a521ca24ac", "old one", 0),
            _chunk("e76c1f93-3e52-5bb4-8d4d-a7d2d5844f79", "old two", 1),
        )
        replacement = (_chunk("389c2968-1db6-52e5-80ac-b8e2e4eb98a1", "new", 0),)

        store.replace_by_metadata(initial, ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]), metadata)
        store.replace_by_metadata(replacement, ([0.0, 0.0, 1.0],), metadata)

        assert store.count(metadata) == 1
        assert store.search([0.0, 0.0, 1.0], limit=2)[0].chunk.text == "new"
    finally:
        store.close()
