import pytest

from paper_research_copilot.domain import PaperChunk, RetrievedChunk
from paper_research_copilot.integrations import ChatCompletion, ChatTokenUsage
from paper_research_copilot.reporting import (
    AnswerGenerator,
    CitationValidationError,
    TruncatedAnswerError,
)


class FakeChatProvider:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        assert "[C1]" in user_prompt
        return self.answer


class FlakyChatProvider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise ValueError("Chat provider returned an empty answer")
        return "Recovered answer [C1]."


class ObservableSequenceProvider:
    def __init__(self, completions: list[ChatCompletion]) -> None:
        self.completions = completions
        self.prompts: list[str] = []

    def complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion:
        self.prompts.append(user_prompt)
        return self.completions[len(self.prompts) - 1]

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("AnswerGenerator should use observable completion metadata")


def _completion(content: str, finish_reason: str) -> ChatCompletion:
    return ChatCompletion(
        content=content,
        finish_reason=finish_reason,
        response_model="answer-model",
        usage=ChatTokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _evidence() -> tuple[RetrievedChunk, ...]:
    return (
        RetrievedChunk(
            citation_id="C1",
            score=0.91,
            chunk=PaperChunk(
                chunk_id="89dc7b16-6840-50ef-9850-e1a521ca24ac",
                document_sha256="a" * 64,
                chunk_index=0,
                chunking_version="chunking_v1",
                title="Agent Paper",
                source_path="agent.pdf",
                page_number=3,
                char_start=0,
                char_end=29,
                text="Agents use tools to take action.",
            ),
        ),
    )


def test_answer_generator_maps_valid_citations() -> None:
    generator = AnswerGenerator(FakeChatProvider("Agents can use tools to act [C1]."))

    answer = generator.generate("How do agents act?", _evidence())

    assert answer.text.endswith("[C1].")
    assert answer.citations[0].page_number == 3
    assert answer.citations[0].excerpt == "Agents use tools to take action."


@pytest.mark.parametrize("marker", ["[1]", "[c1]"])
def test_answer_generator_normalizes_unambiguous_citation_markers(marker: str) -> None:
    generator = AnswerGenerator(FakeChatProvider(f"Agents can use tools to act {marker}."))

    answer = generator.generate("How do agents act?", _evidence())

    assert answer.text == "Agents can use tools to act [C1]."
    assert [citation.citation_id for citation in answer.citations] == ["C1"]


def test_answer_generator_returns_structured_abstention() -> None:
    generator = AnswerGenerator(FakeChatProvider("INSUFFICIENT_EVIDENCE"))

    answer = generator.generate("What is not in the corpus?", _evidence())

    assert answer.status == "insufficient_evidence"
    assert answer.citations == ()


def test_answer_generator_retries_one_empty_provider_response() -> None:
    provider = FlakyChatProvider()
    generator = AnswerGenerator(provider)

    answer = generator.generate("How do agents act?", _evidence())

    assert provider.calls == 2
    assert answer.text == "Recovered answer [C1]."


def test_answer_generator_retries_truncation_with_compact_instruction() -> None:
    provider = ObservableSequenceProvider(
        [
            _completion("", "length"),
            _completion("Compact recovered answer [C1].", "stop"),
        ]
    )
    generator = AnswerGenerator(provider)

    answer = generator.generate("How do agents act?", _evidence())
    trace = generator.trace_for("How do agents act?")

    assert answer.text == "Compact recovered answer [C1]."
    assert len(provider.prompts) == 2
    assert "previous response reached the output token limit" in provider.prompts[1]
    assert [attempt.outcome for attempt in trace.attempts] == ["truncated", "accepted"]
    assert trace.retry_triggered
    assert trace.retry_recovered


def test_answer_generator_rejects_answer_truncated_twice() -> None:
    provider = ObservableSequenceProvider(
        [
            _completion("Partial answer [C1]", "length"),
            _completion("Still partial [C1]", "length"),
        ]
    )
    generator = AnswerGenerator(provider)

    with pytest.raises(TruncatedAnswerError):
        generator.generate("How do agents act?", _evidence())

    trace = generator.trace_for("How do agents act?")
    assert [attempt.finish_reason for attempt in trace.attempts] == ["length", "length"]
    assert trace.final_outcome == "truncated"
    assert not trace.retry_recovered


@pytest.mark.parametrize(
    "answer",
    ["No citation.", "Unsupported claim [C2].", "Unknown numeric source [2]."],
)
def test_answer_generator_rejects_missing_or_unknown_citations(answer: str) -> None:
    generator = AnswerGenerator(FakeChatProvider(answer))

    with pytest.raises(CitationValidationError):
        generator.generate("How do agents act?", _evidence())
