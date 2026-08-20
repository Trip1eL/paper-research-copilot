"""Embedding provider interface and SiliconFlow implementation."""

from collections import OrderedDict
from collections.abc import Sequence
from threading import Lock
from typing import Protocol

from paper_research_copilot.integrations.openai_compatible import OpenAICompatibleTransport


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class CachedEmbeddingProvider:
    """Bounded process-local cache for repeated retrieval query embeddings."""

    def __init__(self, provider: EmbeddingProvider, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("Embedding cache must retain at least one entry")
        self._provider = provider
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._lock = Lock()

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        missing: list[str] = []
        resolved: dict[str, tuple[float, ...]] = {}
        with self._lock:
            for text in dict.fromkeys(texts):
                if text in self._cache:
                    self._cache.move_to_end(text)
                    resolved[text] = self._cache[text]
                else:
                    missing.append(text)
        if missing:
            vectors = self._provider.embed(missing)
            if len(vectors) != len(missing):
                raise ValueError("Embedding provider returned an unexpected vector count")
            with self._lock:
                for text, vector in zip(missing, vectors, strict=True):
                    resolved[text] = tuple(vector)
                    self._cache[text] = resolved[text]
                    self._cache.move_to_end(text)
                while len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)
        return [list(resolved[text]) for text in texts]


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
