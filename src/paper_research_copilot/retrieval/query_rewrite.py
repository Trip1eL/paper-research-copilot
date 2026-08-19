"""Observable query rewriting and multi-query rank fusion."""

import json
import re
import time
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.integrations import ChatProvider
from paper_research_copilot.retrieval.hybrid import fuse_rankings
from paper_research_copilot.retrieval.retriever import CandidateRetriever

QUERY_REWRITE_PROMPT_VERSION = "query_rewrite_v1"

_SYSTEM_PROMPT = """You rewrite academic research questions into English retrieval queries.
Return valid JSON only, with exactly one key named \"queries\".
Do not answer the question.
Do not name or guess paper titles, system names, authors, datasets, or arXiv identifiers.
Preserve technical mechanisms and important contrasts from the original question."""


class QueryRewriteRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    rewritten_queries: tuple[str, ...] = Field(min_length=1)
    model: str
    prompt_version: str
    generation_latency_ms: float = Field(ge=0)


class CachedQueryRewriter:
    """Generate structured rewrites and persist every completed result as JSONL."""

    def __init__(
        self,
        chat_provider: ChatProvider | None,
        *,
        model: str,
        cache_path: Path,
        rewrite_count: int = 3,
        retry_attempts: int = 3,
    ) -> None:
        if rewrite_count < 1:
            raise ValueError("Rewrite count must be at least 1")
        if retry_attempts < 1:
            raise ValueError("Retry attempts must be at least 1")
        self._chat_provider = chat_provider
        self.model = model
        self.cache_path = cache_path
        self.rewrite_count = rewrite_count
        self.retry_attempts = retry_attempts
        self._records = self._load_cache()

    def rewrite(self, question: str) -> tuple[str, ...]:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question must not be empty")
        cached = self._records.get(normalized_question)
        if cached is not None:
            return cached.rewritten_queries

        user_prompt = (
            f"Create exactly {self.rewrite_count} complementary English search queries for the "
            "question below. For a comparison or multi-part question, make the queries cover "
            "different mechanisms or sub-intents. Each query must stand alone and must not infer "
            "a paper or system name.\n\n"
            f"Question:\n{normalized_question}\n\n"
            'Return: {"queries":["query 1","query 2","query 3"]}'
        )
        started = time.perf_counter()
        response = self._complete_with_retry(user_prompt)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        queries = _parse_queries(response, self.rewrite_count, normalized_question)
        record = QueryRewriteRecord(
            question=normalized_question,
            rewritten_queries=queries,
            model=self.model,
            prompt_version=QUERY_REWRITE_PROMPT_VERSION,
            generation_latency_ms=latency_ms,
        )
        self._records[normalized_question] = record
        self._write_cache()
        return queries

    def _complete_with_retry(self, user_prompt: str) -> str:
        if self._chat_provider is None:
            raise LookupError(
                "Query rewrite is missing from the cache and no provider is configured"
            )
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return self._chat_provider.complete(_SYSTEM_PROMPT, user_prompt)
            except ValueError as exc:
                if "empty answer" not in str(exc) or attempt == self.retry_attempts:
                    raise
            time.sleep(0.5 * (2 ** (attempt - 1)))
        raise RuntimeError("Query rewrite retry loop exhausted unexpectedly")

    def record_for(self, question: str) -> QueryRewriteRecord:
        try:
            return self._records[question.strip()]
        except KeyError as exc:
            raise LookupError("Question has not been rewritten") from exc

    def _load_cache(self) -> dict[str, QueryRewriteRecord]:
        if not self.cache_path.is_file():
            return {}
        records = {
            record.question: record
            for line in self.cache_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for record in (QueryRewriteRecord.model_validate_json(line),)
        }
        mismatched = [
            record.question
            for record in records.values()
            if record.model != self.model
            or record.prompt_version != QUERY_REWRITE_PROMPT_VERSION
            or len(record.rewritten_queries) != self.rewrite_count
        ]
        if mismatched:
            raise ValueError(
                "Query rewrite cache does not match the requested model, prompt, or count"
            )
        return records

    def _write_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            self._records[question].model_dump_json() for question in sorted(self._records)
        )
        self.cache_path.write_text(content + "\n", encoding="utf-8")


class MultiQueryRrfRetriever:
    """Fuse Dense and lexical rankings for the original and rewritten queries."""

    def __init__(
        self,
        dense_retriever: CandidateRetriever,
        lexical_retriever: CandidateRetriever,
        query_rewriter: CachedQueryRewriter,
        *,
        candidate_pool_size: int = 50,
        rrf_k: int = 60,
    ) -> None:
        if candidate_pool_size < 1:
            raise ValueError("Candidate pool size must be at least 1")
        if rrf_k < 1:
            raise ValueError("RRF k must be at least 1")
        self._dense_retriever = dense_retriever
        self._lexical_retriever = lexical_retriever
        self._query_rewriter = query_rewriter
        self.candidate_pool_size = candidate_pool_size
        self.rrf_k = rrf_k
        self._queries_by_question: dict[str, tuple[str, ...]] = {}

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        queries = _deduplicate((question.strip(), *self._query_rewriter.rewrite(question)))
        self._queries_by_question[question] = queries
        pool_size = max(top_k, self.candidate_pool_size)
        rankings = tuple(
            ranking
            for query in queries
            for ranking in (
                self._dense_retriever.retrieve(query, pool_size),
                self._lexical_retriever.retrieve(query, pool_size),
            )
        )
        return fuse_rankings(rankings, top_k=top_k, rrf_k=self.rrf_k)

    def queries_for(self, question: str) -> tuple[str, ...]:
        return self._queries_by_question.get(question, ())


def _parse_queries(response: str, count: int, original_question: str) -> tuple[str, ...]:
    cleaned = response.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        payload = json.loads(cleaned)
        raw_queries = payload["queries"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Query rewriter must return a JSON object containing queries") from exc
    if not isinstance(raw_queries, list) or not all(
        isinstance(query, str) for query in raw_queries
    ):
        raise ValueError("Query rewrites must be a JSON string array")
    queries = _deduplicate(tuple(" ".join(query.split()) for query in raw_queries if query.strip()))
    if len(queries) != count:
        raise ValueError(f"Query rewriter returned {len(queries)} unique queries; expected {count}")
    if any(query.casefold() == original_question.casefold() for query in queries):
        raise ValueError("Query rewriter repeated the original question")
    return queries


def _deduplicate(queries: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(query for query in queries if query))


def find_query_rewrite_alias_leaks(
    records: Iterable[QueryRewriteRecord],
    aliases: Iterable[str],
) -> tuple[str, ...]:
    normalized_aliases = tuple(alias.strip() for alias in aliases if alias.strip())
    return tuple(
        f"{record.question} -> {alias}: {query}"
        for record in records
        for query in record.rewritten_queries
        for alias in normalized_aliases
        if alias.casefold() in query.casefold()
    )
