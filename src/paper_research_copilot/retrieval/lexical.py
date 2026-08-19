"""BM25 lexical retrieval over the versioned Qdrant chunk corpus."""

from collections.abc import Sequence
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, cast

import Stemmer  # type: ignore[import-not-found]

from paper_research_copilot.domain import PaperChunk, RetrievedChunk

# bm25s imports a Windows benchmark helper that writes an irrelevant message to stdout.
with redirect_stdout(StringIO()):
    import bm25s  # type: ignore[import-untyped]


class Bm25Retriever:
    """In-memory BM25 index with English stopword removal and stemming."""

    def __init__(
        self,
        chunks: Sequence[PaperChunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if not chunks:
            raise ValueError("BM25 requires at least one chunk")
        if k1 <= 0:
            raise ValueError("BM25 k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("BM25 b must be between 0 and 1")
        self._chunks = tuple(sorted(chunks, key=lambda chunk: chunk.chunk_id))
        self.k1 = k1
        self.b = b
        self._stemmer = Stemmer.Stemmer("english")
        corpus_tokens = bm25s.tokenize(
            [chunk.text for chunk in self._chunks],
            stopwords="en",
            stemmer=self._stemmer,
            show_progress=False,
        )
        self._index: Any = bm25s.BM25(k1=k1, b=b, method="lucene")
        self._index.index(corpus_tokens, show_progress=False)

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        query_tokens = bm25s.tokenize(
            [question],
            stopwords="en",
            stemmer=self._stemmer,
            show_progress=False,
        )
        raw_indices, raw_scores = self._index.retrieve(
            query_tokens,
            k=min(top_k, len(self._chunks)),
            show_progress=False,
        )
        indices = cast(Sequence[int], raw_indices[0])
        scores = cast(Sequence[float], raw_scores[0])
        evidence: list[RetrievedChunk] = []
        for raw_index, raw_score in zip(indices, scores, strict=True):
            score = float(raw_score)
            if score <= 0:
                continue
            evidence.append(
                RetrievedChunk(
                    citation_id=f"C{len(evidence) + 1}",
                    score=score,
                    chunk=self._chunks[int(raw_index)],
                )
            )
        return tuple(evidence)
