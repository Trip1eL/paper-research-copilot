from datetime import UTC, datetime

import httpx

from paper_research_copilot.domain import PaperCandidate
from paper_research_copilot.integrations.scholarly import (
    ArxivSearchProvider,
    rank_and_deduplicate_candidates,
)

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <updated>2026-08-18T12:00:00Z</updated>
    <published>2026-08-10T12:00:00Z</published>
    <title>Agent Memory with Bounded Retrieval</title>
    <summary>We study durable memory and retrieval for autonomous agents.</summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <arxiv:doi>10.1000/EXAMPLE</arxiv:doi>
    <category term="cs.AI"/>
    <link href="http://arxiv.org/abs/2401.01234v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="https://arxiv.org/pdf/2401.01234v2"
          rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

OLD_ID_FEED = b"""<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://arxiv.org/abs/hep-th/9901001v3</id>
    <updated>2001-01-02T00:00:00Z</updated>
    <published>1999-01-01T00:00:00Z</published>
    <title>Legacy Identifier Paper</title>
    <summary>A legacy high energy physics identifier.</summary>
    <author><name>Researcher</name></author>
  </entry>
</feed>"""


def test_arxiv_provider_parses_versioned_atom_metadata() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, content=ATOM_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ArxivSearchProvider(client)
    candidates = provider.search("agent memory retrieval", 5)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.external_id == "2401.01234"
    assert candidate.revision == 2
    assert candidate.identity == "arxiv:2401.01234v2"
    assert candidate.doi == "10.1000/example"
    assert candidate.authors == ("Alice Example", "Bob Example")
    assert candidate.landing_url.startswith("https://")
    assert candidate.search_score > 0
    assert observed_request is not None
    assert observed_request.url.params["max_results"] == "5"
    assert observed_request.url.params["sortBy"] == "relevance"
    client.close()


def test_arxiv_provider_preserves_legacy_identifier_category_prefix() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=OLD_ID_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candidate = ArxivSearchProvider(client).search("legacy physics", 1)[0]

    assert candidate.external_id == "hep-th/9901001"
    assert candidate.revision == 3
    assert candidate.pdf_url == "https://arxiv.org/pdf/hep-th/9901001v3"
    client.close()


def _candidate(
    external_id: str,
    title: str,
    *,
    doi: str | None = None,
    revision: int = 1,
) -> PaperCandidate:
    return PaperCandidate(
        external_id=external_id,
        revision=revision,
        title=title,
        authors=("Researcher",),
        abstract="A paper about autonomous systems and evaluation.",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, revision, tzinfo=UTC),
        landing_url=f"https://arxiv.org/abs/{external_id}v{revision}",
        pdf_url=f"https://arxiv.org/pdf/{external_id}v{revision}",
        doi=doi,
    )


def test_candidate_ranking_is_stable_and_deduplicates_identity_and_doi() -> None:
    candidates = (
        _candidate("2401.00001", "Unrelated vision paper"),
        _candidate("2401.00002", "Agent memory evaluation", doi="10.1/shared"),
        _candidate("2401.00003", "Agent memory", doi="10.1/shared"),
        _candidate("2401.00002", "Agent memory evaluation", doi="10.1/shared"),
    )

    ranked = rank_and_deduplicate_candidates(
        "agent memory evaluation",
        candidates,
        limit=5,
    )

    assert [item.external_id for item in ranked] == ["2401.00002", "2401.00001"]
    assert ranked[0].search_score > ranked[1].search_score
