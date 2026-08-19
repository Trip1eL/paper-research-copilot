from typing import cast

import pytest

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.pipeline import BaseRagPipeline
from paper_research_copilot.reporting import AnswerGenerator
from paper_research_copilot.retrieval import RetrievalMode, RetrieverFactory


def _evidence(label: str) -> tuple[RetrievedChunk, ...]:
    text = f"{label} evidence reaches the answer prompt."
    return (
        RetrievedChunk(
            citation_id="C1",
            score=0.9,
            chunk=PaperChunk(
                chunk_id=f"chunk-{label}",
                document_sha256="a" * 64,
                chunk_index=0,
                chunking_version="chunking_v1",
                paper_id=f"paper-{label}",
                title=f"{label.title()} Paper",
                source_path=f"{label}.pdf",
                page_number=2,
                char_start=0,
                char_end=len(text),
                text=text,
            ),
        ),
    )


class _FixedRetriever:
    def __init__(self, evidence: tuple[RetrievedChunk, ...]) -> None:
        self.evidence = evidence

    def retrieve(self, question: str, top_k: int = 5) -> tuple[RetrievedChunk, ...]:
        return self.evidence[:top_k]


class _RecordingChatProvider:
    def __init__(self) -> None:
        self.user_prompt = ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return "Grounded answer [C1]."


class _ModeFactory(RetrieverFactory):
    def __init__(self) -> None:
        self.retrievers = {
            RetrievalMode.EVIDENCE: _FixedRetriever(_evidence("dense")),
            RetrievalMode.DISCOVERY: _FixedRetriever(_evidence("hybrid")),
        }

    def get(self, mode: RetrievalMode | str) -> _FixedRetriever:
        return self.retrievers[RetrievalMode(mode)]


@pytest.mark.parametrize(
    ("mode", "expected_text", "expected_chunk_id"),
    [
        (RetrievalMode.EVIDENCE, "dense evidence", "chunk-dense"),
        (RetrievalMode.DISCOVERY, "hybrid evidence", "chunk-hybrid"),
    ],
)
def test_selected_mode_evidence_reaches_prompt_and_answer_citation(
    mode: RetrievalMode,
    expected_text: str,
    expected_chunk_id: str,
) -> None:
    chat = _RecordingChatProvider()
    pipeline = BaseRagPipeline(
        parser=cast(object, None),
        chunker=cast(object, None),
        embeddings=cast(object, None),
        vector_store=cast(object, None),
        retrievers=_ModeFactory(),
        answer_generator=AnswerGenerator(chat),
        default_top_k=5,
    )

    answer = pipeline.ask("How does it work?", retrieval_mode=mode)

    assert expected_text in chat.user_prompt
    assert answer.citations[0].chunk_id == expected_chunk_id
