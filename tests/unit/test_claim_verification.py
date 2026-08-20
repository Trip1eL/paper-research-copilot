import json

import pytest

from paper_research_copilot.agent import LlmClaimVerifier
from paper_research_copilot.domain import Answer, Citation, PaperChunk, RetrievedChunk
from paper_research_copilot.integrations import ChatCompletion, ChatTokenUsage


class _SequenceProvider:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion:
        assert "academic RAG answer" in system_prompt
        assert "candidate_answer" in user_prompt
        response = self.responses[self.calls]
        self.calls += 1
        return ChatCompletion(
            content=response,
            finish_reason="stop",
            response_model="fake-gpt",
            usage=ChatTokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        )


def _evidence() -> tuple[RetrievedChunk, ...]:
    text = "ReAct interleaves reasoning traces and task-specific actions."
    return (
        RetrievedChunk(
            citation_id="C1",
            score=0.9,
            chunk=PaperChunk(
                chunk_id="react-1",
                document_sha256="a" * 64,
                chunk_index=0,
                chunking_version="chunking_v1",
                paper_id="react",
                title="ReAct",
                source_path="react.pdf",
                page_number=2,
                char_start=0,
                char_end=len(text),
                text=text,
            ),
        ),
    )


def _answer(text: str) -> Answer:
    evidence = _evidence()[0]
    return Answer(
        question="How does ReAct work?",
        text=text,
        citations=(
            Citation(
                citation_id="C1",
                chunk_id=evidence.chunk.chunk_id,
                paper_id=evidence.chunk.paper_id,
                title=evidence.chunk.title,
                source_path=evidence.chunk.source_path,
                page_number=evidence.chunk.page_number,
                excerpt=evidence.chunk.text,
                retrieval_score=evidence.score,
            ),
        ),
    )


def _payload(
    *,
    verdict: str,
    action: str,
    revised_answer: str | None,
    citation_id: str = "C1",
) -> str:
    return json.dumps(
        {
            "claims": [
                {
                    "claim": "ReAct interleaves reasoning and actions.",
                    "citation_ids": [citation_id],
                    "verdict": verdict,
                    "rationale": "The cited passage directly states the mechanism.",
                }
            ],
            "action": action,
            "revised_answer": revised_answer,
            "rationale": "Claim support was checked against the cited passage.",
            "needs_human_review": False,
        }
    )


def test_claim_verifier_passes_fully_supported_answer() -> None:
    provider = _SequenceProvider(
        _payload(verdict="supported", action="pass", revised_answer=None)
    )
    verifier = LlmClaimVerifier(provider, model="gpt-5.5")
    answer = _answer("ReAct interleaves reasoning and actions [C1].")

    result = verifier.verify(answer.question, answer, _evidence())

    assert result.answer == answer
    assert result.verification.status == "passed"
    assert result.verification.claims[0].verdict == "supported"
    assert result.verification.attempts == 1
    assert result.verification.usage.total_tokens == 150


def test_claim_verifier_applies_one_bounded_revision() -> None:
    provider = _SequenceProvider(
        _payload(
            verdict="unsupported",
            action="revise",
            revised_answer="ReAct interleaves reasoning and actions [C1].",
        )
    )
    verifier = LlmClaimVerifier(provider, model="gpt-5.5")
    answer = _answer(
        "ReAct interleaves reasoning and actions and guarantees perfect results [C1]."
    )

    result = verifier.verify(answer.question, answer, _evidence())

    assert result.verification.status == "revised"
    assert result.answer.text == "ReAct interleaves reasoning and actions [C1]."
    assert result.answer.citations[0].citation_id == "C1"
    assert provider.calls == 1


def test_claim_verifier_retries_invalid_citation_contract() -> None:
    provider = _SequenceProvider(
        _payload(
            verdict="supported",
            action="pass",
            revised_answer=None,
            citation_id="C9",
        ),
        _payload(verdict="supported", action="pass", revised_answer=None),
    )
    verifier = LlmClaimVerifier(provider, model="gpt-5.5")
    answer = _answer("ReAct interleaves reasoning and actions [C1].")

    result = verifier.verify(answer.question, answer, _evidence())

    assert result.verification.attempts == 2
    assert result.verification.usage.total_tokens == 300
    assert provider.calls == 2


def test_claim_verifier_rejects_repeated_invalid_output() -> None:
    invalid = _payload(
        verdict="supported",
        action="pass",
        revised_answer=None,
        citation_id="C9",
    )
    verifier = LlmClaimVerifier(_SequenceProvider(invalid, invalid), model="gpt-5.5")
    answer = _answer("ReAct interleaves reasoning and actions [C1].")

    with pytest.raises(ValueError, match="failed after 2 attempts"):
        verifier.verify(answer.question, answer, _evidence())
