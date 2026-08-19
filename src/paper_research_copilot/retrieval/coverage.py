"""Query decomposition and quota-preserving retrieval for multi-intent questions."""

import json
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import RetrievedChunk
from paper_research_copilot.integrations import ChatProvider, RerankerProvider
from paper_research_copilot.retrieval.retriever import CandidateRetriever

QUERY_DECOMPOSITION_PROMPT_VERSION = "query_decomposition_v1"

_SYSTEM_PROMPT = """You decompose academic comparison questions for retrieval.
Return valid JSON only, with exactly one key named "sub_queries".
Do not answer the question.
Do not name, identify, or guess paper titles, method names, system names, authors, datasets,
or arXiv identifiers unless that exact name already appears in the user's question.
Each sub-query must preserve one explicit mechanism or comparison side from the original question,
stand alone as a retrieval query, and avoid adding outside knowledge."""


class QueryDecompositionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    sub_queries: tuple[str, ...] = Field(min_length=2, max_length=4)
    model: str
    prompt_version: str
    generation_latency_ms: float = Field(ge=0)


class CachedQueryDecomposer:
    def __init__(
        self,
        chat_provider: ChatProvider | None,
        *,
        model: str,
        cache_path: Path,
        sub_query_count: int = 2,
        retry_attempts: int = 3,
    ) -> None:
        if not 2 <= sub_query_count <= 4:
            raise ValueError("Sub-query count must be between 2 and 4")
        if retry_attempts < 1:
            raise ValueError("Retry attempts must be at least 1")
        self._chat_provider = chat_provider
        self.model = model
        self.cache_path = cache_path
        self.sub_query_count = sub_query_count
        self.retry_attempts = retry_attempts
        self._records = self._load_cache()

    def decompose(self, question: str) -> tuple[str, ...]:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question must not be empty")
        cached = self._records.get(normalized_question)
        if cached is not None:
            return cached.sub_queries
        user_prompt = (
            f"Split the comparison question below into exactly {self.sub_query_count} independent "
            "retrieval sub-queries. Preserve the descriptive wording for each comparison side. "
            "Do not infer the names of the methods being described.\n\n"
            f"Question:\n{normalized_question}\n\n"
            '{"sub_queries":["first mechanism query","second mechanism query"]}'
        )
        started = time.perf_counter()
        sub_queries = self._generate_sub_queries(user_prompt, normalized_question)
        record = QueryDecompositionRecord(
            question=normalized_question,
            sub_queries=sub_queries,
            model=self.model,
            prompt_version=QUERY_DECOMPOSITION_PROMPT_VERSION,
            generation_latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        self._records[normalized_question] = record
        self._write_cache()
        return sub_queries

    def record_for(self, question: str) -> QueryDecompositionRecord:
        try:
            return self._records[question.strip()]
        except KeyError as exc:
            raise LookupError("Question has not been decomposed") from exc

    def _generate_sub_queries(
        self,
        user_prompt: str,
        original_question: str,
    ) -> tuple[str, ...]:
        if self._chat_provider is None:
            raise LookupError(
                "Query decomposition is missing from the cache and no provider is configured"
            )
        last_error: ValueError | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self._chat_provider.complete(_SYSTEM_PROMPT, user_prompt)
                return _parse_sub_queries(
                    response,
                    count=self.sub_query_count,
                    original_question=original_question,
                )
            except ValueError as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
        raise ValueError(
            f"Query decomposition failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error

    def _load_cache(self) -> dict[str, QueryDecompositionRecord]:
        if not self.cache_path.is_file():
            return {}
        records = {
            record.question: record
            for line in self.cache_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for record in (QueryDecompositionRecord.model_validate_json(line),)
        }
        mismatched = [
            record.question
            for record in records.values()
            if record.model != self.model
            or record.prompt_version != QUERY_DECOMPOSITION_PROMPT_VERSION
            or len(record.sub_queries) != self.sub_query_count
        ]
        if mismatched:
            raise ValueError(
                "Query decomposition cache does not match the requested model, prompt, or count"
            )
        return records

    def _write_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            self._records[question].model_dump_json() for question in sorted(self._records)
        )
        self.cache_path.write_text(content + "\n", encoding="utf-8")


@dataclass(frozen=True)
class CoverageTrace:
    sub_queries: tuple[str, ...]
    candidate_counts: tuple[int, ...]
    selected_counts: tuple[int, ...]
    reranker_model: str | None
    decomposition_latency_ms: float
    decomposition_generation_latency_ms: float
    hybrid_latency_ms: tuple[float, ...]
    reranker_latency_ms: tuple[float, ...]
    total_latency_ms: float


class CoverageAwareRetriever:
    """Retrieve each sub-intent independently and preserve its quota in the final Top-K."""

    def __init__(
        self,
        candidate_retriever: CandidateRetriever,
        decomposer: CachedQueryDecomposer,
        *,
        reranker: RerankerProvider | None = None,
        candidate_pool_per_query: int = 30,
    ) -> None:
        if candidate_pool_per_query < 1:
            raise ValueError("Candidate pool per query must be at least 1")
        self._candidate_retriever = candidate_retriever
        self._decomposer = decomposer
        self._reranker = reranker
        self.candidate_pool_per_query = candidate_pool_per_query
        self._traces: dict[str, CoverageTrace] = {}

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        if top_k < 1:
            raise ValueError("Top-K must be at least 1")
        total_started = time.perf_counter()
        decomposition_started = time.perf_counter()
        sub_queries = self._decomposer.decompose(question)
        decomposition_latency_ms = (time.perf_counter() - decomposition_started) * 1000
        ranking_results = tuple(self._ranking_for(sub_query) for sub_query in sub_queries)
        rankings = tuple(result[0] for result in ranking_results)
        merged, selected_counts = coverage_round_robin(rankings, top_k=top_k)
        decomposition_record = self._decomposer.record_for(question)
        self._traces[question] = CoverageTrace(
            sub_queries=sub_queries,
            candidate_counts=tuple(len(ranking) for ranking in rankings),
            selected_counts=selected_counts,
            reranker_model=self._reranker.model if self._reranker else None,
            decomposition_latency_ms=round(decomposition_latency_ms, 2),
            decomposition_generation_latency_ms=(decomposition_record.generation_latency_ms),
            hybrid_latency_ms=tuple(result[1] for result in ranking_results),
            reranker_latency_ms=tuple(result[2] for result in ranking_results),
            total_latency_ms=round((time.perf_counter() - total_started) * 1000, 2),
        )
        return merged

    def trace_for(self, question: str) -> CoverageTrace:
        try:
            return self._traces[question]
        except KeyError as exc:
            raise LookupError("Question has not been coverage-retrieved") from exc

    def _ranking_for(
        self,
        sub_query: str,
    ) -> tuple[tuple[RetrievedChunk, ...], float, float]:
        retrieval_started = time.perf_counter()
        candidates = self._candidate_retriever.retrieve(
            sub_query,
            self.candidate_pool_per_query,
        )
        retrieval_latency_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        if self._reranker is None or not candidates:
            return candidates, retrieval_latency_ms, 0.0
        reranker_started = time.perf_counter()
        scores = self._reranker.score(
            sub_query,
            [candidate.chunk.text for candidate in candidates],
        )
        reranker_latency_ms = round((time.perf_counter() - reranker_started) * 1000, 2)
        ranking = tuple(
            candidate.model_copy(update={"score": score})
            for _, (candidate, score) in sorted(
                enumerate(zip(candidates, scores, strict=True)),
                key=lambda item: (-item[1][1], item[0], item[1][0].chunk.chunk_id),
            )
        )
        return ranking, retrieval_latency_ms, reranker_latency_ms


def coverage_round_robin(
    rankings: Sequence[Sequence[RetrievedChunk]],
    *,
    top_k: int,
) -> tuple[tuple[RetrievedChunk, ...], tuple[int, ...]]:
    if top_k < 1:
        raise ValueError("Top-K must be at least 1")
    if not rankings:
        return (), ()
    selected: list[RetrievedChunk] = []
    selected_ids: set[str] = set()
    selected_counts = [0 for _ in rankings]
    positions = [0 for _ in rankings]
    while len(selected) < top_k:
        added = False
        for ranking_index, ranking in enumerate(rankings):
            while (
                positions[ranking_index] < len(ranking)
                and ranking[positions[ranking_index]].chunk.chunk_id in selected_ids
            ):
                positions[ranking_index] += 1
            if positions[ranking_index] >= len(ranking):
                continue
            candidate = ranking[positions[ranking_index]]
            positions[ranking_index] += 1
            selected.append(candidate)
            selected_ids.add(candidate.chunk.chunk_id)
            selected_counts[ranking_index] += 1
            added = True
            if len(selected) == top_k:
                break
        if not added:
            break
    return (
        tuple(
            candidate.model_copy(update={"citation_id": f"C{rank}"})
            for rank, candidate in enumerate(selected, start=1)
        ),
        tuple(selected_counts),
    )


def find_decomposition_alias_leaks(
    records: Iterable[QueryDecompositionRecord],
    aliases: Iterable[str],
) -> tuple[str, ...]:
    normalized_aliases = tuple(alias.strip() for alias in aliases if alias.strip())
    return tuple(
        f"{record.question} -> {alias}: {sub_query}"
        for record in records
        for sub_query in record.sub_queries
        for alias in normalized_aliases
        if alias.casefold() in sub_query.casefold()
        and alias.casefold() not in record.question.casefold()
    )


def _parse_sub_queries(
    response: str,
    *,
    count: int,
    original_question: str,
) -> tuple[str, ...]:
    cleaned = response.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        payload = json.loads(cleaned)
        raw_queries = payload["sub_queries"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(
            "Query decomposer must return a JSON object containing sub_queries"
        ) from exc
    if not isinstance(raw_queries, list) or not all(
        isinstance(query, str) for query in raw_queries
    ):
        raise ValueError("Decomposed sub-queries must be a JSON string array")
    queries = tuple(
        dict.fromkeys(" ".join(query.split()) for query in raw_queries if query.strip())
    )
    if len(queries) != count:
        raise ValueError(
            f"Query decomposer returned {len(queries)} unique queries; expected {count}"
        )
    if any(query.casefold() == original_question.casefold() for query in queries):
        raise ValueError("Query decomposer repeated the original question")
    return queries
