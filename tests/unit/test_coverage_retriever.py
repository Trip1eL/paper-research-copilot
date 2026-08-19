from pathlib import Path

import pytest

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval import (
    CachedQueryDecomposer,
    CoverageAwareRetriever,
    QueryDecompositionRecord,
    coverage_round_robin,
    find_decomposition_alias_leaks,
)


class _FakeChatProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "Do not name, identify, or guess paper titles" in system_prompt
        assert "exactly 2" in user_prompt
        return self.response


class _InvalidThenValidProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return "not json"
        return '{"sub_queries":["first side","second side"]}'


class _FakeCandidateRetriever:
    def __init__(self, rankings: dict[str, tuple[RetrievedChunk, ...]]) -> None:
        self.rankings = rankings
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.calls.append((question, top_k))
        return self.rankings[question][:top_k]


class _FakeReranker:
    model = "fake-reranker"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def score(self, query: str, documents: object) -> tuple[float, ...]:
        normalized = tuple(documents)  # type: ignore[arg-type]
        self.calls.append((query, normalized))
        return tuple(float(index) for index in range(len(normalized)))


def _candidate(number: int, *, paper_id: str | None = None) -> RetrievedChunk:
    text = f"candidate evidence {number}"
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=1 / number,
        chunk=PaperChunk(
            chunk_id=f"chunk-{number}",
            document_sha256="a" * 64,
            chunk_index=number,
            chunking_version="chunking_v1",
            paper_id=paper_id or f"paper-{number}",
            title=f"Paper {number}",
            source_path=f"paper-{number}.pdf",
            page_number=number,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


def _decomposer(tmp_path: Path, response: str) -> CachedQueryDecomposer:
    return CachedQueryDecomposer(
        _FakeChatProvider(response),
        model="test-model",
        cache_path=tmp_path / "decompositions.jsonl",
        sub_query_count=2,
    )


def test_query_decomposer_parses_fenced_json_and_reuses_cache(tmp_path: Path) -> None:
    provider = _FakeChatProvider('```json\n{"sub_queries":["first side","second side"]}\n```')
    cache_path = tmp_path / "decompositions.jsonl"
    decomposer = CachedQueryDecomposer(
        provider,
        model="test-model",
        cache_path=cache_path,
        sub_query_count=2,
    )

    assert decomposer.decompose("compare two mechanisms") == ("first side", "second side")
    assert decomposer.decompose("compare two mechanisms") == ("first side", "second side")
    assert provider.calls == 1

    cached = CachedQueryDecomposer(
        None,
        model="test-model",
        cache_path=cache_path,
        sub_query_count=2,
    )
    assert cached.decompose("compare two mechanisms") == ("first side", "second side")


def test_query_decomposer_rejects_duplicate_sub_queries(tmp_path: Path) -> None:
    decomposer = _decomposer(
        tmp_path,
        '{"sub_queries":["same mechanism", "same   mechanism"]}',
    )

    with pytest.raises(ValueError, match="unique queries"):
        decomposer.decompose("compare two mechanisms")


def test_query_decomposer_retries_invalid_structured_output(tmp_path: Path) -> None:
    provider = _InvalidThenValidProvider()
    decomposer = CachedQueryDecomposer(
        provider,
        model="test-model",
        cache_path=tmp_path / "decompositions.jsonl",
        sub_query_count=2,
    )

    assert decomposer.decompose("compare two mechanisms") == ("first side", "second side")
    assert provider.calls == 2


def test_query_decomposition_alias_leak_check_ignores_name_already_in_question() -> None:
    records = (
        QueryDecompositionRecord(
            question="Compare the first mechanism with Toolformer",
            sub_queries=("ReAct observations", "Toolformer API filtering"),
            model="test-model",
            prompt_version="query_decomposition_v1",
            generation_latency_ms=10,
        ),
    )

    leaks = find_decomposition_alias_leaks(records, ("ReAct", "Toolformer"))

    assert len(leaks) == 1
    assert "-> ReAct:" in leaks[0]
    assert "-> Toolformer:" not in leaks[0]


def test_coverage_round_robin_preserves_each_ranking_and_deduplicates() -> None:
    shared = _candidate(1)
    first = (shared, _candidate(2), _candidate(3))
    second = (shared, _candidate(4), _candidate(5))

    merged, counts = coverage_round_robin((first, second), top_k=4)

    assert [item.chunk.chunk_id for item in merged] == [
        "chunk-1",
        "chunk-4",
        "chunk-2",
        "chunk-5",
    ]
    assert [item.citation_id for item in merged] == ["C1", "C2", "C3", "C4"]
    assert counts == (2, 2)


def test_coverage_retriever_uses_each_sub_query_without_reranker(tmp_path: Path) -> None:
    decomposer = _decomposer(
        tmp_path,
        '{"sub_queries":["first mechanism", "second mechanism"]}',
    )
    candidates = _FakeCandidateRetriever(
        {
            "first mechanism": (_candidate(1), _candidate(2)),
            "second mechanism": (_candidate(3), _candidate(4)),
        }
    )
    retriever = CoverageAwareRetriever(
        candidates,
        decomposer,
        candidate_pool_per_query=2,
    )

    results = retriever.retrieve("compare two mechanisms", top_k=4)
    trace = retriever.trace_for("compare two mechanisms")

    assert [item.chunk.chunk_id for item in results] == [
        "chunk-1",
        "chunk-3",
        "chunk-2",
        "chunk-4",
    ]
    assert candidates.calls == [("first mechanism", 2), ("second mechanism", 2)]
    assert trace.selected_counts == (2, 2)
    assert trace.reranker_model is None
    assert trace.reranker_latency_ms == (0.0, 0.0)


def test_coverage_retriever_reranks_inside_each_sub_query(tmp_path: Path) -> None:
    decomposer = _decomposer(
        tmp_path,
        '{"sub_queries":["first mechanism", "second mechanism"]}',
    )
    candidates = _FakeCandidateRetriever(
        {
            "first mechanism": (_candidate(1), _candidate(2)),
            "second mechanism": (_candidate(3), _candidate(4)),
        }
    )
    reranker = _FakeReranker()
    retriever = CoverageAwareRetriever(
        candidates,
        decomposer,
        reranker=reranker,
        candidate_pool_per_query=2,
    )

    results = retriever.retrieve("compare two mechanisms", top_k=4)
    trace = retriever.trace_for("compare two mechanisms")

    assert [item.chunk.chunk_id for item in results] == [
        "chunk-2",
        "chunk-4",
        "chunk-1",
        "chunk-3",
    ]
    assert [call[0] for call in reranker.calls] == ["first mechanism", "second mechanism"]
    assert trace.reranker_model == "fake-reranker"
    assert len(trace.reranker_latency_ms) == 2
