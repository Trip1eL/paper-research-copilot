from pathlib import Path

from pytest import MonkeyPatch

from paper_research_copilot.config import Settings
from paper_research_copilot.domain import PaperChunk
from paper_research_copilot.pipeline import build_federated_retrieval_runtime


class _Embeddings:
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def embed(self, texts) -> list[list[float]]:
        self.calls.append(tuple(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


def _chunk(
    chunk_id: str,
    text: str,
    *,
    corpus_id: str,
    paper_id: str,
) -> PaperChunk:
    return PaperChunk(
        chunk_id=chunk_id,
        document_sha256=("a" if corpus_id == "curated" else "b") * 64,
        chunk_index=0,
        chunking_version="chunking_v1",
        corpus_id=corpus_id,
        corpus_version=1,
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        source_path=f"{paper_id}.pdf",
        page_number=1,
        char_start=0,
        char_end=len(text),
        text=text,
    )


def test_dynamic_points_refresh_bm25_and_enter_federated_results(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    embeddings = _Embeddings()
    monkeypatch.setattr(
        "paper_research_copilot.pipeline.SiliconFlowEmbeddingProvider",
        lambda **_: embeddings,
    )
    settings = Settings(
        siliconflow_base_url="https://example.test/v1",
        siliconflow_api_key="test-key",
        embedding_dimension=3,
        qdrant_path=tmp_path / "curated",
        dynamic_qdrant_path=tmp_path / "dynamic",
        qdrant_collection="curated",
        dynamic_qdrant_collection="dynamic",
    )
    runtime = build_federated_retrieval_runtime(settings)
    try:
        curated = _chunk(
            "89dc7b16-6840-50ef-9850-e1a521ca24ac",
            "Curated planning evidence.",
            corpus_id="curated",
            paper_id="curated-paper",
        )
        runtime.curated_vector_store.upsert((curated,), ([1.0, 0.0, 0.0],))

        initial = runtime.retriever.retrieve("newly acquired memory", top_k=3)

        dynamic = _chunk(
            "e76c1f93-3e52-5bb4-8d4d-a7d2d5844f79",
            "Newly acquired memory evidence.",
            corpus_id="paper-dynamic",
            paper_id="dynamic-paper",
        )
        runtime.dynamic_vector_store.upsert((dynamic,), ([1.0, 0.0, 0.0],))

        refreshed = runtime.retriever.retrieve("newly acquired memory", top_k=3)

        assert [item.chunk.paper_id for item in initial] == ["curated-paper"]
        assert {item.chunk.paper_id for item in refreshed} == {
            "curated-paper",
            "dynamic-paper",
        }
        assert embeddings.calls == [("newly acquired memory",)]
    finally:
        runtime.close()
