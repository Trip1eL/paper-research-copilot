from pathlib import Path

import pytest

from paper_research_copilot.retrieval import (
    CachedQueryRewriter,
    QueryRewriteRecord,
    find_query_rewrite_alias_leaks,
)


class _FakeChatProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "Do not name or guess paper titles" in system_prompt
        assert "Create exactly 3" in user_prompt
        return self.response


class _EmptyThenValidProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise ValueError("Chat provider returned an empty answer")
        return (
            '{"queries":["external tool selection",'
            '"reasoning and environment actions","observation feedback loop"]}'
        )


def test_query_rewriter_persists_and_reuses_structured_cache(tmp_path: Path) -> None:
    provider = _FakeChatProvider(
        '{"queries":["external tool selection",'
        '"reasoning and environment actions","observation feedback loop"]}'
    )
    cache_path = tmp_path / "rewrites.jsonl"
    rewriter = CachedQueryRewriter(
        provider,
        model="test-model",
        cache_path=cache_path,
        rewrite_count=3,
    )

    first = rewriter.rewrite("智能体如何使用工具？")
    second = rewriter.rewrite("智能体如何使用工具？")

    assert first == second
    assert provider.calls == 1
    assert cache_path.is_file()
    assert rewriter.record_for("智能体如何使用工具？").model == "test-model"


def test_query_rewriter_rejects_non_json_response(tmp_path: Path) -> None:
    rewriter = CachedQueryRewriter(
        _FakeChatProvider("external tool selection"),
        model="test-model",
        cache_path=tmp_path / "rewrites.jsonl",
        rewrite_count=3,
    )

    with pytest.raises(ValueError, match="JSON object"):
        rewriter.rewrite("智能体如何使用工具？")


def test_query_rewriter_retries_empty_provider_response(tmp_path: Path) -> None:
    provider = _EmptyThenValidProvider()
    rewriter = CachedQueryRewriter(
        provider,
        model="test-model",
        cache_path=tmp_path / "rewrites.jsonl",
        rewrite_count=3,
    )

    queries = rewriter.rewrite("智能体如何使用工具？")

    assert len(queries) == 3
    assert provider.calls == 2


def test_query_rewrite_alias_leak_check() -> None:
    record = QueryRewriteRecord(
        question="How does the method act?",
        rewritten_queries=("ReAct tool use", "reasoning with actions"),
        model="test-model",
        prompt_version="query_rewrite_v1",
        generation_latency_ms=10,
    )

    leaks = find_query_rewrite_alias_leaks((record,), ("react", "toolformer"))

    assert len(leaks) == 1
    assert "react" in leaks[0].casefold()
