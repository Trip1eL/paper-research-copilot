"""Generate an answer and validate its citation markers."""

import re
import time
from collections.abc import Sequence
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import Answer, Citation, RetrievedChunk
from paper_research_copilot.integrations import (
    ChatCompletion,
    ChatProvider,
    ChatTokenUsage,
    ObservableChatProvider,
)
from paper_research_copilot.reporting.prompts import SYSTEM_PROMPT, build_user_prompt


class CitationValidationError(RuntimeError):
    """Raised when an answer does not cite the supplied evidence correctly."""


class TruncatedAnswerError(RuntimeError):
    """Raised when every allowed generation attempt ends at the token limit."""


class AnswerAttemptTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempt: int = Field(ge=1)
    finish_reason: str
    outcome: Literal["accepted", "empty", "truncated", "provider_error", "invalid_citation"]
    content_length: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    response_model: str | None = None
    usage: ChatTokenUsage
    error: str | None = None


class AnswerGenerationTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempts: tuple[AnswerAttemptTrace, ...]
    retry_triggered: bool
    retry_recovered: bool
    final_outcome: str


class AnswerGenerator:
    _CITATION_PATTERN = re.compile(r"\[(C[1-9][0-9]*)\]")
    _CITATION_LIKE_PATTERN = re.compile(r"\[([Cc]?[0-9]+)\]")
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    _COMPACT_RETRY_INSTRUCTION = """

The previous response reached the output token limit. Retry with a compact answer:
- use at most 500 Chinese characters or 300 English words;
- answer only the requested comparison or facts;
- keep all material claims cited;
- do not add background, examples, or a references section.
"""

    def __init__(self, chat_provider: ChatProvider, *, retry_attempts: int = 2) -> None:
        if retry_attempts < 1:
            raise ValueError("Retry attempts must be at least 1")
        self._chat_provider = chat_provider
        self.retry_attempts = retry_attempts
        self._traces: dict[str, AnswerGenerationTrace] = {}

    def generate(self, question: str, evidence: Sequence[RetrievedChunk]) -> Answer:
        if not evidence:
            raise ValueError("Cannot generate an answer without retrieved evidence")

        base_user_prompt = build_user_prompt(question, evidence)
        attempts: list[AnswerAttemptTrace] = []
        for attempt in range(1, self.retry_attempts + 1):
            user_prompt = (
                base_user_prompt
                if attempt == 1 or not any(item.outcome == "truncated" for item in attempts)
                else base_user_prompt + self._COMPACT_RETRY_INSTRUCTION
            )
            started = time.perf_counter()
            try:
                completion = self._complete_with_metadata(SYSTEM_PROMPT, user_prompt)
            except ValueError as exc:
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                if "empty answer" in str(exc):
                    attempts.append(
                        self._attempt_trace(
                            attempt,
                            latency_ms,
                            outcome="empty",
                            finish_reason="unknown",
                            error=str(exc),
                        )
                    )
                    if attempt < self.retry_attempts:
                        continue
                else:
                    attempts.append(
                        self._attempt_trace(
                            attempt,
                            latency_ms,
                            outcome="provider_error",
                            finish_reason="provider_error",
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
                self._store_trace(question, attempts)
                raise
            except Exception as exc:
                attempts.append(
                    self._attempt_trace(
                        attempt,
                        round((time.perf_counter() - started) * 1000, 2),
                        outcome="provider_error",
                        finish_reason="provider_error",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                self._store_trace(question, attempts)
                raise

            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            answer_text = completion.content.strip()
            if completion.finish_reason == "length":
                attempts.append(
                    self._attempt_trace(
                        attempt,
                        latency_ms,
                        outcome="truncated",
                        completion=completion,
                        error="Chat completion reached the output token limit",
                    )
                )
                if attempt < self.retry_attempts:
                    continue
                self._store_trace(question, attempts)
                raise TruncatedAnswerError(
                    f"Answer remained truncated after {self.retry_attempts} attempts"
                )
            if not answer_text:
                attempts.append(
                    self._attempt_trace(
                        attempt,
                        latency_ms,
                        outcome="empty",
                        completion=completion,
                        error="Chat provider returned an empty answer",
                    )
                )
                if attempt < self.retry_attempts:
                    continue
                self._store_trace(question, attempts)
                raise ValueError("Chat provider returned an empty answer")

            try:
                answer = self._build_answer(question, answer_text, evidence)
            except CitationValidationError as exc:
                attempts.append(
                    self._attempt_trace(
                        attempt,
                        latency_ms,
                        outcome="invalid_citation",
                        completion=completion,
                        error=str(exc),
                    )
                )
                self._store_trace(question, attempts)
                raise
            attempts.append(
                self._attempt_trace(
                    attempt,
                    latency_ms,
                    outcome="accepted",
                    completion=completion,
                )
            )
            self._store_trace(question, attempts)
            return answer
        raise RuntimeError("Answer retry loop exhausted unexpectedly")

    def trace_for(self, question: str) -> AnswerGenerationTrace:
        try:
            return self._traces[question]
        except KeyError as exc:
            raise LookupError("Question has not been generated") from exc

    def _complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion:
        if hasattr(self._chat_provider, "complete_with_metadata"):
            provider = cast(ObservableChatProvider, self._chat_provider)
            return provider.complete_with_metadata(system_prompt, user_prompt)
        return ChatCompletion(
            content=self._chat_provider.complete(system_prompt, user_prompt),
            finish_reason=None,
            usage=ChatTokenUsage(),
        )

    def _build_answer(
        self,
        question: str,
        answer_text: str,
        evidence: Sequence[RetrievedChunk],
    ) -> Answer:
        if answer_text.strip() == self.INSUFFICIENT_EVIDENCE:
            return Answer(
                question=question,
                text=self.INSUFFICIENT_EVIDENCE,
                citations=(),
                status="insufficient_evidence",
            )
        evidence_by_id = {item.citation_id: item for item in evidence}
        answer_text = self._normalize_citation_markers(answer_text, evidence_by_id)
        cited_ids = tuple(dict.fromkeys(self._CITATION_PATTERN.findall(answer_text)))
        if not cited_ids:
            raise CitationValidationError("The generated answer contains no citation markers")

        unknown_ids = [
            citation_id for citation_id in cited_ids if citation_id not in evidence_by_id
        ]
        if unknown_ids:
            raise CitationValidationError(
                f"The generated answer contains unknown citations: {', '.join(unknown_ids)}"
            )

        citations = tuple(
            self._to_citation(evidence_by_id[citation_id]) for citation_id in cited_ids
        )
        return Answer(question=question, text=answer_text, citations=citations)

    def _normalize_citation_markers(
        self,
        answer_text: str,
        evidence_by_id: dict[str, RetrievedChunk],
    ) -> str:
        unknown_markers: list[str] = []

        def replace(match: re.Match[str]) -> str:
            marker = match.group(1)
            number = marker[1:] if marker[:1].casefold() == "c" else marker
            citation_id = f"C{int(number)}"
            if citation_id not in evidence_by_id:
                unknown_markers.append(match.group(0))
                return match.group(0)
            return f"[{citation_id}]"

        normalized = self._CITATION_LIKE_PATTERN.sub(replace, answer_text)
        if unknown_markers:
            raise CitationValidationError(
                "The generated answer contains unknown citation-like markers: "
                + ", ".join(dict.fromkeys(unknown_markers))
            )
        return normalized

    @staticmethod
    def _attempt_trace(
        attempt: int,
        latency_ms: float,
        *,
        outcome: Literal["accepted", "empty", "truncated", "provider_error", "invalid_citation"],
        finish_reason: str = "unknown",
        completion: ChatCompletion | None = None,
        error: str | None = None,
    ) -> AnswerAttemptTrace:
        return AnswerAttemptTrace(
            attempt=attempt,
            finish_reason=(completion.finish_reason or "unknown") if completion else finish_reason,
            outcome=outcome,
            content_length=len(completion.content) if completion else 0,
            latency_ms=latency_ms,
            response_model=completion.response_model if completion else None,
            usage=completion.usage if completion else ChatTokenUsage(),
            error=error,
        )

    def _store_trace(
        self,
        question: str,
        attempts: Sequence[AnswerAttemptTrace],
    ) -> None:
        final_outcome = attempts[-1].outcome
        self._traces[question] = AnswerGenerationTrace(
            attempts=tuple(attempts),
            retry_triggered=len(attempts) > 1,
            retry_recovered=len(attempts) > 1 and final_outcome == "accepted",
            final_outcome=final_outcome,
        )

    @staticmethod
    def _to_citation(evidence: RetrievedChunk) -> Citation:
        chunk = evidence.chunk
        return Citation(
            citation_id=evidence.citation_id,
            chunk_id=chunk.chunk_id,
            paper_id=chunk.paper_id,
            title=chunk.title,
            source_path=chunk.source_path,
            page_number=chunk.page_number,
            excerpt=chunk.text,
            retrieval_score=evidence.score,
        )
