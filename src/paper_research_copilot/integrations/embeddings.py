"""Embedding provider interface and SiliconFlow implementation."""

from collections.abc import Sequence
from typing import Protocol

from paper_research_copilot.integrations.openai_compatible import OpenAICompatibleTransport


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SiliconFlowEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "BAAI/bge-m3",
        dimension: int = 1024,
        batch_size: int = 32,
    ) -> None:
        self._transport = OpenAICompatibleTransport(base_url, api_key)
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = self._transport.post(
                "embeddings",
                {"model": self._model, "input": batch, "encoding_format": "float"},
            )
            raw_items = response.get("data")
            if not isinstance(raw_items, list):
                raise ValueError("Embedding response is missing the data list")
            items = sorted(raw_items, key=lambda item: item["index"])
            batch_vectors = [item["embedding"] for item in items]
            if len(batch_vectors) != len(batch):
                raise ValueError("Embedding response count does not match input count")
            if any(len(vector) != self._dimension for vector in batch_vectors):
                raise ValueError(
                    f"Embedding dimension does not match configured size {self._dimension}"
                )
            vectors.extend(batch_vectors)
        return vectors
