"""Bounded arXiv Atom API search adapter."""

from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

import httpx

from paper_research_copilot.domain import PaperCandidate
from paper_research_copilot.integrations.scholarly.base import (
    rank_and_deduplicate_candidates,
)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM = "http://www.w3.org/2005/Atom"
ARXIV = "http://arxiv.org/schemas/atom"
_ARXIV_ID = re.compile(
    r"^(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7}))v(?P<revision>\d+)$",
    re.IGNORECASE,
)
_CAMEL_CASE_TERM = re.compile(
    r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+)(?![A-Za-z0-9])"
)
_QUERY_WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "does",
    "for",
    "from",
    "how",
    "in",
    "into",
    "of",
    "on",
    "the",
    "through",
    "to",
    "use",
    "uses",
    "using",
    "what",
    "with",
}


class ArxivSearchError(RuntimeError):
    """Raised when arXiv metadata cannot be fetched or validated."""


class ArxivSearchProvider:
    provider_name = "arxiv"

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        api_url: str = ARXIV_API_URL,
        timeout: float = 20,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self._client = client or httpx.Client(
            headers={"User-Agent": "paper-research-copilot/2.0"}
        )
        self._owns_client = client is None
        self._api_url = api_url
        self._timeout = timeout
        self._max_attempts = max_attempts

    def search(self, query: str, limit: int) -> tuple[PaperCandidate, ...]:
        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("Academic search query must not be empty")
        if not 1 <= limit <= 10:
            raise ValueError("arXiv search limit must be between 1 and 10")
        search_query = _compact_academic_query(normalized)
        response = self._request(
            {
                "search_query": f'all:"{_escape_query(search_query)}"',
                "start": "0",
                "max_results": str(limit),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        candidates = _parse_feed(response.content)
        return rank_and_deduplicate_candidates(normalized, candidates, limit=limit)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, params: dict[str, str]) -> httpx.Response:
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(
                    self._api_url,
                    params=params,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                if not retryable or attempt == self._max_attempts:
                    raise ArxivSearchError(
                        f"arXiv search failed with HTTP {exc.response.status_code}"
                    ) from exc
            except httpx.TransportError as exc:
                if attempt == self._max_attempts:
                    raise ArxivSearchError("arXiv search transport failed") from exc
            time.sleep(0.25 * attempt)
        raise ArxivSearchError("arXiv search retry loop exhausted")


def _parse_feed(content: bytes) -> tuple[PaperCandidate, ...]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ArxivSearchError("arXiv returned invalid Atom XML") from exc
    candidates = tuple(_parse_entry(entry) for entry in root.findall(f"{{{ATOM}}}entry"))
    return candidates


def _parse_entry(entry: ElementTree.Element) -> PaperCandidate:
    entry_url = _required_text(entry, f"{{{ATOM}}}id")
    path = unquote(urlsplit(entry_url).path)
    if "/abs/" not in path:
        raise ArxivSearchError(f"Unsupported arXiv entry URL: {entry_url}")
    raw_id = path.split("/abs/", 1)[1].rstrip("/")
    match = _ARXIV_ID.fullmatch(raw_id)
    if match is None:
        raise ArxivSearchError(f"Unsupported arXiv identifier: {raw_id}")
    external_id = match.group("id")
    revision = int(match.group("revision"))
    links = entry.findall(f"{{{ATOM}}}link")
    landing_url = next(
        (
            link.attrib["href"]
            for link in links
            if link.attrib.get("rel") == "alternate" and "href" in link.attrib
        ),
        f"https://arxiv.org/abs/{external_id}v{revision}",
    )
    pdf_url = next(
        (
            link.attrib["href"]
            for link in links
            if link.attrib.get("title") == "pdf" and "href" in link.attrib
        ),
        f"https://arxiv.org/pdf/{external_id}v{revision}",
    )
    return PaperCandidate(
        external_id=external_id,
        revision=revision,
        title=_required_text(entry, f"{{{ATOM}}}title"),
        authors=tuple(
            _required_text(author, f"{{{ATOM}}}name")
            for author in entry.findall(f"{{{ATOM}}}author")
        ),
        abstract=_required_text(entry, f"{{{ATOM}}}summary"),
        published_at=_parse_datetime(_required_text(entry, f"{{{ATOM}}}published")),
        updated_at=_parse_datetime(_required_text(entry, f"{{{ATOM}}}updated")),
        landing_url=_https_url(landing_url),
        pdf_url=_https_url(pdf_url),
        doi=_optional_text(entry, f"{{{ARXIV}}}doi"),
        categories=tuple(
            category.attrib["term"]
            for category in entry.findall(f"{{{ATOM}}}category")
            if category.attrib.get("term")
        ),
    )


def _required_text(parent: ElementTree.Element, path: str) -> str:
    value = _optional_text(parent, path)
    if value is None:
        raise ArxivSearchError(f"arXiv entry is missing required field: {path}")
    return value


def _optional_text(parent: ElementTree.Element, path: str) -> str | None:
    element = parent.find(path)
    if element is None or element.text is None:
        return None
    normalized = " ".join(element.text.split())
    return normalized or None


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ArxivSearchError("arXiv timestamp is missing timezone information")
    return parsed


def _https_url(value: str) -> str:
    return re.sub(r"^http://", "https://", value, count=1, flags=re.IGNORECASE)


def _escape_query(value: str) -> str:
    return value.replace("\\", " ").replace('"', " ")


def _compact_academic_query(query: str, *, max_terms: int = 4) -> str:
    """Keep arXiv phrase searches short enough to recover method-specific papers."""
    normalized = " ".join(query.split())
    terms = _QUERY_WORD.findall(normalized)
    if len(terms) <= max_terms:
        return normalized

    method_names: list[str] = _CAMEL_CASE_TERM.findall(normalized)
    if method_names:
        return method_names[0]

    distinctive = [
        term
        for term in terms
        if term.casefold() not in _QUERY_STOPWORDS
    ]
    selected = distinctive[:max_terms] or terms[:max_terms]
    return " ".join(selected)
