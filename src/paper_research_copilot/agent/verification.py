"""Bounded production Claim-Evidence verification and one-shot answer revision."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.agent.models import ClaimAssessment, ClaimVerification
from paper_research_copilot.domain import Answer, Citation, RetrievedChunk
from paper_research_copilot.integrations import (
    ChatCompletion,
    ChatTokenUsage,
    ObservableChatProvider,
)

CLAIM_VERIFIER_PROMPT_VERSION = "claim_verifier_v1"
_CITATION_PATTERN = re.compile(r"\[(C[1-9][0-9]*)\]")

_SYSTEM_PROMPT = """You verify an academic RAG answer against its cited evidence.
Do not use outside knowledge and do not answer the research question yourself.
Split the answer into at most 8 material factual claims. For each claim, judge whether the
specific cited evidence supports it. A verdict must be supported, partially_supported, or
unsupported. Citation IDs must come from the candidate answer.

If every material claim is supported, set action to pass and revised_answer to null.
If any material claim is partially supported or unsupported, set action to revise and provide a
complete revised answer that removes unsupported details or uses more cautious wording. The revised
answer may use only citation markers already present in the candidate answer. If no meaningful claim
remains, revised_answer must be exactly INSUFFICIENT_EVIDENCE.

Set needs_human_review for conflicting, ambiguous, or incomplete evidence. Return valid JSON only,
without Markdown fences."""


class _ClaimPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str = Field(min_length=1)
    citation_ids: tuple[str, ...]
    verdict: Literal["supported", "partially_supported", "unsupported"]
    rationale: str = Field(min_length=1)


class _VerificationPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[_ClaimPayload, ...] = Field(min_length=1, max_length=8)
    action: Literal["pass", "revise"]
    revised_answer: str | None = None
    rationale: str = Field(min_length=1)
    needs_human_review: bool = False

    @model_validator(mode="after")
    def validate_action(self) -> _VerificationPayload:
        requires_revision = any(item.verdict != "supported" for item in self.claims)
        if requires_revision != (self.action == "revise"):
            raise ValueError("Action must revise exactly when a Claim is not fully supported")
        if self.action == "revise" and not (self.revised_answer or "").strip():
            raise ValueError("Revision action requires revised_answer")
        if self.action == "pass" and self.revised_answer is not None:
            raise ValueError("Pass action must not include revised_answer")
        return self


class ClaimVerificationOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    answer: Answer
    verification: ClaimVerification


class LlmClaimVerifier:
    """Verify cited claims and apply at most one model-proposed revision."""

    def __init__(
        self,
        provider: ObservableChatProvider,
        *,
        model: str,
        retry_attempts: int = 2,
    ) -> None:
        if retry_attempts < 1:
            raise ValueError("Retry attempts must be at least 1")
        self._provider = provider
        self.model = model
        self.retry_attempts = retry_attempts

    def verify(
        self,
        question: str,
        answer: Answer,
        evidence: Sequence[RetrievedChunk],
    ) -> ClaimVerificationOutcome:
        if answer.status != "answered":
            raise ValueError("Only answered results can be Claim-verified")
        prompt = _build_user_prompt(question, answer)
        started = time.perf_counter()
        completions: list[ChatCompletion] = []
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            repair = ""
            if last_error is not None:
                repair = (
                    "\n\nThe previous response violated the output contract. "
                    f"Fix this error and return the full JSON again: {last_error}"
                )
            try:
                completion = self._provider.complete_with_metadata(
                    _SYSTEM_PROMPT,
                    prompt + repair,
                )
                completions.append(completion)
                if completion.finish_reason == "length":
                    raise ValueError("Claim verifier response was truncated")
                payload = _parse_payload(completion.content)
                _validate_claim_citations(payload, answer)
                final_answer = (
                    answer
                    if payload.action == "pass"
                    else _build_revised_answer(
                        question,
                        payload.revised_answer or "",
                        answer,
                        evidence,
                    )
                )
                if payload.action == "revise" and final_answer.text == answer.text:
                    raise ValueError("Revised answer must differ from the original answer")
                verification = ClaimVerification(
                    status="passed" if payload.action == "pass" else "revised",
                    claims=tuple(
                        ClaimAssessment(
                            claim_id=f"CL{index}",
                            claim=item.claim,
                            citation_ids=item.citation_ids,
                            verdict=item.verdict,
                            rationale=item.rationale,
                        )
                        for index, item in enumerate(payload.claims, 1)
                    ),
                    rationale=payload.rationale,
                    needs_human_review=payload.needs_human_review,
                    model=self.model,
                    prompt_version=CLAIM_VERIFIER_PROMPT_VERSION,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    attempts=attempt,
                    usage=_sum_usage(completions),
                    response_model=completion.response_model,
                )
                return ClaimVerificationOutcome(
                    answer=final_answer,
                    verification=verification,
                )
            except Exception as exc:
                last_error = exc
        raise ValueError(
            f"Claim verifier failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error


def _build_user_prompt(question: str, answer: Answer) -> str:
    payload = {
        "question": question,
        "candidate_answer": answer.text,
        "cited_evidence": [
            {
                "citation_id": citation.citation_id,
                "paper_id": citation.paper_id,
                "title": citation.title,
                "page_number": citation.page_number,
                "evidence": citation.excerpt,
            }
            for citation in answer.citations
        ],
        "required_output": {
            "claims": [
                {
                    "claim": "material factual claim",
                    "citation_ids": ["C1"],
                    "verdict": "supported|partially_supported|unsupported",
                    "rationale": "concise evidence-based reason",
                }
            ],
            "action": "pass|revise",
            "revised_answer": "full revised answer or null",
            "rationale": "overall concise rationale",
            "needs_human_review": "boolean",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_payload(content: str) -> _VerificationPayload:
    stripped = content.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Claim verifier response does not contain a JSON object")
    try:
        return _VerificationPayload.model_validate_json(stripped[start : end + 1])
    except ValueError as exc:
        raise ValueError(f"Invalid Claim verifier payload: {exc}") from exc


def _validate_claim_citations(payload: _VerificationPayload, answer: Answer) -> None:
    known_ids = {citation.citation_id for citation in answer.citations}
    unknown = {
        citation_id
        for claim in payload.claims
        for citation_id in claim.citation_ids
        if citation_id not in known_ids
    }
    if unknown:
        raise ValueError(
            "Claim verifier used unknown Citation IDs: " + ", ".join(sorted(unknown))
        )


def _build_revised_answer(
    question: str,
    text: str,
    original: Answer,
    evidence: Sequence[RetrievedChunk],
) -> Answer:
    normalized = text.strip()
    if normalized == "INSUFFICIENT_EVIDENCE":
        return Answer(
            question=question,
            text=normalized,
            citations=(),
            status="insufficient_evidence",
        )
    cited_ids = tuple(dict.fromkeys(_CITATION_PATTERN.findall(normalized)))
    if not cited_ids:
        raise ValueError("Revised answer must contain Citation markers")
    original_by_id = {citation.citation_id: citation for citation in original.citations}
    evidence_ids = {item.citation_id for item in evidence}
    unknown = [
        citation_id
        for citation_id in cited_ids
        if citation_id not in original_by_id or citation_id not in evidence_ids
    ]
    if unknown:
        raise ValueError(
            "Revised answer used unavailable Citation IDs: " + ", ".join(unknown)
        )
    citations: tuple[Citation, ...] = tuple(original_by_id[item] for item in cited_ids)
    return Answer(question=question, text=normalized, citations=citations)


def _sum_usage(completions: Sequence[ChatCompletion]) -> ChatTokenUsage:
    input_values = [item.usage.input_tokens for item in completions]
    output_values = [item.usage.output_tokens for item in completions]
    total_values = [item.usage.total_tokens for item in completions]
    return ChatTokenUsage(
        input_tokens=_optional_sum(input_values),
        output_tokens=_optional_sum(output_values),
        total_tokens=_optional_sum(total_values),
    )


def _optional_sum(values: Sequence[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None
