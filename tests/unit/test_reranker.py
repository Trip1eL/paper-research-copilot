from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.integrations.reranking import SiliconFlowRerankerProvider
from paper_research_copilot.retrieval import RerankingRetriever


class _FakeTransport:
    def post(self, resource: str, payload: object) -> dict[str, object]:
        assert resource == "rerank"
        return {
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.2},
            ]
        }


class _FakeCandidateRetriever:
    def __init__(self, candidates: tuple[RetrievedChunk, ...]) -> None:
        self.candidates = candidates

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self.candidates[:top_k]


class _FakeReranker:
    model = "fake-reranker"

    def score(self, query: str, documents: object) -> tuple[float, ...]:
        return (0.1, 0.9, 0.5)


def _candidate(number: int, score: float) -> RetrievedChunk:
    text = f"candidate evidence {number}"
    return RetrievedChunk(
        citation_id=f"C{number}",
        score=score,
        chunk=PaperChunk(
            chunk_id=f"chunk-{number}",
            document_sha256="a" * 64,
            chunk_index=number,
            chunking_version="chunking_v1",
            paper_id=f"paper-{number}",
            title=f"Paper {number}",
            source_path=f"paper-{number}.pdf",
            page_number=number,
            char_start=0,
            char_end=len(text),
            text=text,
        ),
    )


def test_siliconflow_reranker_maps_scores_back_to_document_order() -> None:
    provider = SiliconFlowRerankerProvider(
        "https://provider.example/v1",
        "secret",
        transport=_FakeTransport(),  # type: ignore[arg-type]
    )

    scores = provider.score("query", ("first", "second"))

    assert scores == (0.2, 0.9)


def test_reranking_retriever_records_rank_changes() -> None:
    retriever = RerankingRetriever(
        _FakeCandidateRetriever((_candidate(1, 0.9), _candidate(2, 0.8), _candidate(3, 0.7))),
        _FakeReranker(),
        candidate_pool_size=3,
    )

    results = retriever.retrieve("question", top_k=2)
    trace = retriever.trace_for("question")

    assert [result.chunk.chunk_id for result in results] == ["chunk-2", "chunk-3"]
    assert [result.citation_id for result in results] == ["C1", "C2"]
    assert trace.candidate_count == 3
    assert trace.candidates[0].original_rank == 1
    assert trace.candidates[0].reranked_rank == 3
