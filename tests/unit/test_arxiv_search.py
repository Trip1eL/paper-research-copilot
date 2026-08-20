from datetime import UTC, datetime

import httpx

from paper_research_copilot.domain import PaperCandidate
from paper_research_copilot.integrations.scholarly import (
    ArxivSearchProvider,
    evaluate_candidate_relevance,
    extract_explicit_entities,
    rank_and_deduplicate_candidates,
    select_relevant_candidates,
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
    assert observed_request.url.params["search_query"] == 'all:"agent memory retrieval"'
    client.close()


def test_arxiv_provider_compacts_long_query_to_distinctive_method_name() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, content=ATOM_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ArxivSearchProvider(client).search(
        "How does MemReranker improve reasoning-aware agent memory retrieval?",
        3,
    )

    assert observed_request is not None
    assert observed_request.url.params["search_query"] == 'all:"MemReranker"'
    client.close()


def test_arxiv_provider_compacts_long_generic_query_to_four_content_terms() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, content=ATOM_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ArxivSearchProvider(client).search(
        "How does reasoning aware reranking improve retrieval for agent memory?",
        3,
    )

    assert observed_request is not None
    assert observed_request.url.params["search_query"] == (
        'all:"reasoning aware reranking improve"'
    )
    client.close()


def test_arxiv_provider_combines_short_acronym_with_research_context() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, content=ATOM_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ArxivSearchProvider(client).search(
        "SAGE 如何评测并改进 Deep Research Agents 的 retrieval 能力？",
        5,
    )

    assert observed_request is not None
    assert observed_request.url.params["search_query"] == (
        'all:"SAGE" AND all:"Deep Research Agents"'
    )
    client.close()


def test_arxiv_provider_preserves_hyphenated_model_identity() -> None:
    observed_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_request
        observed_request = request
        return httpx.Response(200, content=ATOM_FEED, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ArxivSearchProvider(client).search(
        "GPT-7 Agent 在 SWE-bench Verified 上的官方解决率是多少？",
        5,
    )

    assert extract_explicit_entities("GPT-7 Agent") == ("GPT-7",)
    assert observed_request is not None
    assert observed_request.url.params["search_query"] == 'all:"GPT-7"'
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


def test_candidate_relevance_requires_exact_named_entity() -> None:
    candidate = _candidate("2601.00001", "GPT Agents for Software Engineering")

    decision = evaluate_candidate_relevance(
        "GPT-7 Agent 在 SWE-bench Verified 上的官方解决率是多少？",
        candidate,
    )

    assert not decision.accepted
    assert decision.required_entities == ("GPT-7",)
    assert decision.reason == "Missing explicit entity: GPT-7"


def test_candidate_relevance_requires_context_for_short_acronym() -> None:
    wrong = _candidate("2601.00002", "SAGE for Spatial Scene Generation")
    target = PaperCandidate(
        **_candidate("2602.05975", "SAGE: Evaluating Deep Research Agents").model_dump(
            exclude={"title", "abstract"}
        ),
        title="SAGE: Evaluating Deep Research Agents",
        abstract="A benchmark for retrieval and evidence synthesis in research agents.",
    )
    query = "SAGE 如何评测并改进 Deep Research Agents 的 retrieval 能力？"

    wrong_decision = evaluate_candidate_relevance(query, wrong)
    target_decision = evaluate_candidate_relevance(query, target)

    assert not wrong_decision.accepted
    assert target_decision.accepted
    assert set(target_decision.matched_context_terms) >= {"deep", "research", "agents"}


def test_candidate_relevance_rejects_same_name_from_another_domain() -> None:
    wrong = _candidate(
        "2607.21125",
        "Causal-AgentIR: Self-Evolving Causal Memory for Image Restoration Agents",
    )
    target = PaperCandidate(
        **_candidate("2603.04384", "AgentIR: Reasoning-Aware Retrieval").model_dump(
            exclude={"title", "abstract"}
        ),
        title="AgentIR: Reasoning-Aware Retrieval for Deep Research Agents",
        abstract="A retrieval model that embeds an agent reasoning trace with its query.",
    )
    query = "AgentIR 如何为 Deep Research Agents 实现 reasoning-aware retrieval？"

    assert not evaluate_candidate_relevance(query, wrong).accepted
    assert evaluate_candidate_relevance(query, target).accepted


def test_candidate_relevance_allows_exact_entity_only_query() -> None:
    target = _candidate("2603.04384", "AgentIR: Reasoning-Aware Retrieval")

    decision = evaluate_candidate_relevance("AgentIR", target)

    assert decision.accepted


def test_named_entity_selection_downloads_only_top_ranked_candidate() -> None:
    target = PaperCandidate(
        **_candidate("2603.04384", "AgentIR: Reasoning-Aware Retrieval").model_dump(
            exclude={"title", "abstract"}
        ),
        title="AgentIR: Reasoning-Aware Retrieval for Deep Research Agents",
        abstract="The retriever embeds reasoning traces with queries from research agents.",
    )
    related = PaperCandidate(
        **_candidate("2607.21126", "AgentIR: Adaptive Retrieval").model_dump(
            exclude={"title", "abstract"}
        ),
        title="AgentIR: Adaptive Retrieval for Conversational Agents",
        abstract="A reasoning-aware retrieval substrate for long-term research tasks.",
    )

    selected = select_relevant_candidates(
        "AgentIR reasoning-aware retrieval for research agents",
        (target, related),
        limit=2,
    )

    assert selected == (target,)
