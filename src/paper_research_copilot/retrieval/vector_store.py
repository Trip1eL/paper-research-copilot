"""Qdrant-backed dense vector storage for paper chunks."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from qdrant_client import QdrantClient, models

from paper_research_copilot.domain import PaperChunk, RetrievedChunk


@dataclass(frozen=True)
class VectorSearchResult:
    evidence: RetrievedChunk
    vector: tuple[float, ...]


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: str,
        dimension: int,
        *,
        path: Path | None = None,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        if bool(path) == bool(url):
            raise ValueError("Configure exactly one of Qdrant path or URL")
        self._collection_name = collection_name
        self.dimension = dimension
        self._client = (
            QdrantClient(path=str(path))
            if path is not None
            else QdrantClient(url=url, api_key=api_key)
        )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def ensure_collection(self) -> None:
        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimension,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(self, chunks: Sequence[PaperChunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts must match")
        if any(len(vector) != self.dimension for vector in vectors):
            raise ValueError(f"Every vector must have dimension {self.dimension}")
        self.ensure_collection()
        self._client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector=list(vector),
                    payload=chunk.model_dump(mode="json"),
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
            wait=True,
        )

    def replace_by_metadata(
        self,
        chunks: Sequence[PaperChunk],
        vectors: Sequence[Sequence[float]],
        metadata: dict[str, str | int | bool],
    ) -> None:
        if not metadata:
            raise ValueError("Replacement metadata filter cannot be empty")
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and vector counts must match")
        self.ensure_collection()
        metadata_filter = self._metadata_filter(metadata)
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(filter=metadata_filter),
            wait=True,
        )
        self.upsert(chunks, vectors)

    def count(self, metadata: dict[str, str | int | bool] | None = None) -> int:
        if not self._client.collection_exists(self.collection_name):
            return 0
        result = self._client.count(
            collection_name=self.collection_name,
            count_filter=self._metadata_filter(metadata) if metadata else None,
            exact=True,
        )
        return result.count

    def list_chunks(
        self,
        metadata: dict[str, str | int | bool] | None = None,
        *,
        page_size: int = 256,
    ) -> tuple[PaperChunk, ...]:
        if page_size < 1:
            raise ValueError("Page size must be at least 1")
        if not self._client.collection_exists(self.collection_name):
            return ()
        chunks: list[PaperChunk] = []
        offset: models.ExtendedPointId | None = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self.collection_name,
                scroll_filter=self._metadata_filter(metadata) if metadata else None,
                limit=page_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(
                PaperChunk.model_validate(record.payload)
                for record in records
                if record.payload is not None
            )
            if offset is None:
                break
        return tuple(sorted(chunks, key=lambda chunk: chunk.chunk_id))

    def get_vectors(self, chunk_ids: Sequence[str]) -> dict[str, tuple[float, ...]]:
        if not chunk_ids or not self._client.collection_exists(self.collection_name):
            return {}
        records = self._client.retrieve(
            collection_name=self.collection_name,
            ids=list(chunk_ids),
            with_payload=True,
            with_vectors=True,
        )
        vectors: dict[str, tuple[float, ...]] = {}
        for record in records:
            if record.payload is None:
                continue
            chunk = PaperChunk.model_validate(record.payload)
            vectors[chunk.chunk_id] = self._dense_vector(record.vector)
        return vectors

    def search(self, query_vector: Sequence[float], limit: int) -> tuple[RetrievedChunk, ...]:
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector must have dimension {self.dimension}")
        if not self._client.collection_exists(self.collection_name):
            return ()

        result = self._client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            limit=limit,
            with_payload=True,
        )
        evidence: list[RetrievedChunk] = []
        for index, point in enumerate(result.points, start=1):
            if point.payload is None:
                continue
            evidence.append(
                RetrievedChunk(
                    citation_id=f"C{index}",
                    score=point.score,
                    chunk=PaperChunk.model_validate(point.payload),
                )
            )
        return tuple(evidence)

    def search_with_vectors(
        self,
        query_vector: Sequence[float],
        limit: int,
    ) -> tuple[VectorSearchResult, ...]:
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector must have dimension {self.dimension}")
        if not self._client.collection_exists(self.collection_name):
            return ()

        result = self._client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )
        candidates: list[VectorSearchResult] = []
        for point in result.points:
            if point.payload is None:
                continue
            candidates.append(
                VectorSearchResult(
                    evidence=RetrievedChunk(
                        citation_id=f"C{len(candidates) + 1}",
                        score=point.score,
                        chunk=PaperChunk.model_validate(point.payload),
                    ),
                    vector=self._dense_vector(point.vector),
                )
            )
        return tuple(candidates)

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _dense_vector(raw_vector: object) -> tuple[float, ...]:
        if not isinstance(raw_vector, list) or any(
            not isinstance(value, (int, float)) for value in raw_vector
        ):
            raise TypeError("Expected an unnamed dense vector from Qdrant")
        dense_vector = cast(list[float], raw_vector)
        return tuple(float(value) for value in dense_vector)

    @staticmethod
    def _metadata_filter(metadata: dict[str, str | int | bool]) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
                for key, value in metadata.items()
            ]
        )
