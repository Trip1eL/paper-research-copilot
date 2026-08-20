"""Public contracts and deterministic candidate selection for academic search."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from paper_research_copilot.domain import PaperCandidate


class AcademicSearchProvider(Protocol):
    def search(self, query: str, limit: int) -> tuple[PaperCandidate, ...]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class CandidateRelevanceDecision:
    """Explain why a metadata candidate is or is not safe to download."""

    accepted: bool
    reason: str
    required_entities: tuple[str, ...]
    matched_context_terms: tuple[str, ...]


_NAMED_ENTITY = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"[A-Z]{2,10}(?:-\d+(?:\.\d+)*)?"
    r"|[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+"
    r")(?![A-Za-z0-9]|-[a-z])"
)
_GENERIC_ACRONYMS = {"AI", "API", "BM25", "LLM", "MMR", "PDF", "RAG", "RRF"}
_CONTEXT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "best",
    "by",
    "does",
    "for",
    "from",
    "how",
    "in",
    "into",
    "method",
    "methods",
    "model",
    "models",
    "of",
    "on",
    "paper",
    "papers",
    "the",
    "through",
    "to",
    "use",
    "uses",
    "using",
    "what",
    "which",
    "with",
}


def rank_and_deduplicate_candidates(
    query: str,
    candidates: Sequence[PaperCandidate],
    *,
    limit: int,
) -> tuple[PaperCandidate, ...]:
    """Apply explainable lexical relevance and stable identity/DOI deduplication."""

    if limit < 1:
        raise ValueError("Candidate limit must be at least one")
    query_tokens = _tokens(query)
    scored = [
        candidate.model_copy(update={"search_score": _score(candidate, query_tokens)})
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            -item.search_score,
            -item.updated_at.timestamp(),
            item.identity,
        )
    )
    selected: list[PaperCandidate] = []
    seen_identities: set[str] = set()
    seen_dois: set[str] = set()
    for candidate in scored:
        if candidate.identity in seen_identities:
            continue
        if candidate.doi is not None and candidate.doi in seen_dois:
            continue
        selected.append(candidate)
        seen_identities.add(candidate.identity)
        if candidate.doi is not None:
            seen_dois.add(candidate.doi)
        if len(selected) == limit:
            break
    return tuple(selected)


def evaluate_candidate_relevance(
    query: str,
    candidate: PaperCandidate,
) -> CandidateRelevanceDecision:
    """Validate entity identity and lexical context before expensive ingestion."""

    entities = extract_explicit_entities(query)
    metadata = f"{candidate.title} {candidate.abstract}"
    missing_entities = tuple(
        entity for entity in entities if not _contains_entity(metadata, entity)
    )
    context_terms = _context_terms(query, entities)
    metadata_tokens = _tokens(metadata)
    matched_context = tuple(term for term in context_terms if term in metadata_tokens)
    if missing_entities:
        return CandidateRelevanceDecision(
            accepted=False,
            reason=f"Missing explicit entity: {', '.join(missing_entities)}",
            required_entities=entities,
            matched_context_terms=matched_context,
        )

    minimum_context = 2
    if entities and len(context_terms) < minimum_context:
        return CandidateRelevanceDecision(
            accepted=True,
            reason="All explicit entities matched; query has no additional context constraint",
            required_entities=entities,
            matched_context_terms=matched_context,
        )
    if len(matched_context) >= minimum_context:
        return CandidateRelevanceDecision(
            accepted=True,
            reason="Explicit entities and query context matched candidate metadata",
            required_entities=entities,
            matched_context_terms=matched_context,
        )
    return CandidateRelevanceDecision(
        accepted=False,
        reason=(
            f"Candidate matched {len(matched_context)} context terms; "
            f"at least {minimum_context} are required"
        ),
        required_entities=entities,
        matched_context_terms=matched_context,
    )


def select_relevant_candidates(
    query: str,
    candidates: Sequence[PaperCandidate],
    *,
    limit: int,
) -> tuple[PaperCandidate, ...]:
    if limit < 1:
        raise ValueError("Candidate limit must be at least one")
    relevant = tuple(
        candidate
        for candidate in candidates
        if evaluate_candidate_relevance(query, candidate).accepted
    )
    effective_limit = 1 if extract_explicit_entities(query) else limit
    return relevant[:effective_limit]


def extract_explicit_entities(query: str) -> tuple[str, ...]:
    """Extract method/model names whose identity must survive candidate search."""

    selected: list[str] = []
    seen: set[str] = set()
    for match in _NAMED_ENTITY.finditer(query):
        entity = match.group(0)
        key = entity.casefold()
        if entity.upper() in _GENERIC_ACRONYMS or key in seen:
            continue
        selected.append(entity)
        seen.add(key)
    return tuple(selected)


def _score(candidate: PaperCandidate, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0
    title = _tokens(candidate.title)
    abstract = _tokens(candidate.abstract)
    categories = {item.casefold() for item in candidate.categories}
    title_matches = len(query_tokens & title)
    abstract_matches = len(query_tokens & abstract)
    category_matches = len(query_tokens & categories)
    coverage = len(query_tokens & (title | abstract)) / len(query_tokens)
    return round(
        title_matches * 3 + abstract_matches + category_matches * 0.5 + coverage,
        6,
    )


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)
        if len(token) >= 2
    }


def _context_terms(query: str, entities: Sequence[str]) -> tuple[str, ...]:
    entity_tokens = {token for entity in entities for token in _tokens(entity)}
    selected: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]*", query):
        normalized = token.casefold()
        if (
            len(normalized) < 2
            or normalized in _CONTEXT_STOPWORDS
            or normalized in entity_tokens
            or normalized in seen
        ):
            continue
        selected.append(normalized)
        seen.add(normalized)
    return tuple(selected)


def _contains_entity(text: str, entity: str) -> bool:
    return re.search(
        rf"(?<![-A-Za-z0-9]){re.escape(entity)}(?![-A-Za-z0-9])",
        text,
        flags=re.IGNORECASE,
    ) is not None
