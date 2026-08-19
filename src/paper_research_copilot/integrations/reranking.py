"""Reranker provider interface and SiliconFlow implementation."""

from collections.abc import Sequence
from typing import Protocol

from paper_research_copilot.integrations.openai_compatible import OpenAICompatibleTransport


class RerankerProvider(Protocol):
    @property
    def model(self) -> str: ...

    def score(self, query: str, documents: Sequence[str]) -> tuple[float, ...]: ...


class SiliconFlowRerankerProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "BAAI/bge-reranker-v2-m3",
        *,
        transport: OpenAICompatibleTransport | None = None,
    ) -> None:
        self._transport = transport or OpenAICompatibleTransport(
            base_url,
            api_key,
            timeout=120.0,
        )
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def score(self, query: str, documents: Sequence[str]) -> tuple[float, ...]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Reranker query must not be empty")
        if not documents:
            return ()
        if any(not document.strip() for document in documents):
            raise ValueError("Reranker documents must not be empty")
        response = self._transport.post(
            "rerank",
            {
                "model": self._model,
                "query": normalized_query,
                "documents": list(documents),
                "top_n": len(documents),
                "return_documents": False,
            },
        )
        raw_results = response.get("results")
        if not isinstance(raw_results, list):
            raise ValueError("Reranker response is missing the results list")
        scores: list[float | None] = [None] * len(documents)
        for item in raw_results:
            if not isinstance(item, dict):
                raise ValueError("Reranker result must be an object")
            index = item.get("index")
            score = item.get("relevance_score")
            if not isinstance(index, int) or not 0 <= index < len(documents):
                raise ValueError("Reranker result contains an invalid document index")
            if scores[index] is not None:
                raise ValueError("Reranker response contains a duplicate document index")
            if not isinstance(score, int | float):
                raise ValueError("Reranker result contains an invalid relevance score")
            scores[index] = float(score)
        if any(score is None for score in scores):
            raise ValueError("Reranker response count does not match document count")
        return tuple(score for score in scores if score is not None)
