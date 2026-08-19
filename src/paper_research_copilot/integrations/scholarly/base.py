"""Public contracts and deterministic candidate selection for academic search."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from paper_research_copilot.domain import PaperCandidate


class AcademicSearchProvider(Protocol):
    def search(self, query: str, limit: int) -> tuple[PaperCandidate, ...]: ...

    def close(self) -> None: ...


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
