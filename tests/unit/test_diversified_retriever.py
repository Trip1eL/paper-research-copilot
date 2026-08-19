from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.retrieval import DiversifiedDenseRetriever


def _candidate(
    citation_number: int,
    *,
    paper_id: str,
    page: int,
    score: float,
) -> RetrievedChunk:
    return RetrievedChunk(
        citation_id=f"C{citation_number}",
        score=score,
        chunk=PaperChunk(
            chunk_id=f"chunk-{citation_number}",
            document_sha256="a" * 64,
            chunk_index=citation_number - 1,
            chunking_version="chunking_v1",
            paper_id=paper_id,
            title=paper_id,
            source_path=f"{paper_id}.pdf",
            page_number=page,
            char_start=0,
            char_end=10,
            text="agent text",
        ),
    )


class _FakeDenseRetriever:
    def __init__(self, candidates: tuple[RetrievedChunk, ...]) -> None:
        self.candidates = candidates
        self.requested_top_k: int | None = None

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        self.requested_top_k = top_k
        return self.candidates[:top_k]


def test_diversification_removes_same_page_duplicates_and_limits_each_paper() -> None:
    dense = _FakeDenseRetriever(
        (
            _candidate(1, paper_id="paper-a", page=1, score=0.99),
            _candidate(2, paper_id="paper-a", page=1, score=0.98),
            _candidate(3, paper_id="paper-a", page=2, score=0.97),
            _candidate(4, paper_id="paper-a", page=3, score=0.96),
            _candidate(5, paper_id="paper-b", page=1, score=0.95),
            _candidate(6, paper_id="paper-c", page=1, score=0.94),
        )
    )
    retriever = DiversifiedDenseRetriever(
        dense,
        candidate_pool_size=6,
        max_chunks_per_paper=2,
        max_chunks_per_page=1,
    )

    results = retriever.retrieve("question", top_k=4)

    assert dense.requested_top_k == 6
    assert [(item.chunk.paper_id, item.chunk.page_number) for item in results] == [
        ("paper-a", 1),
        ("paper-a", 2),
        ("paper-b", 1),
        ("paper-c", 1),
    ]
    assert [item.score for item in results] == [0.99, 0.97, 0.95, 0.94]
    assert [item.citation_id for item in results] == ["C1", "C2", "C3", "C4"]


def test_diversification_returns_fewer_results_when_constraints_exhaust_pool() -> None:
    dense = _FakeDenseRetriever(
        (
            _candidate(1, paper_id="paper-a", page=1, score=0.99),
            _candidate(2, paper_id="paper-a", page=1, score=0.98),
        )
    )
    retriever = DiversifiedDenseRetriever(
        dense,
        candidate_pool_size=2,
        max_chunks_per_paper=1,
        max_chunks_per_page=1,
    )

    results = retriever.retrieve("question", top_k=3)

    assert len(results) == 1
    assert results[0].citation_id == "C1"
