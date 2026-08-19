"""Prompts for evidence-grounded question answering."""

from collections.abc import Sequence

from paper_research_copilot.domain import RetrievedChunk

ANSWER_PROMPT_VERSION = "answer_v2"

SYSTEM_PROMPT = """You are a careful academic research assistant.
Answer the user's question using only the supplied evidence.
Write in the same language as the question and keep the answer clear and concise.
Cite every factual claim with one or more citation markers such as [C1] or [C1][C2].
Never invent a citation marker.
If the evidence is insufficient to answer the question, respond with exactly:
INSUFFICIENT_EVIDENCE
Do not add a separate references section; the application renders sources separately."""


def build_user_prompt(question: str, evidence: Sequence[RetrievedChunk]) -> str:
    context_blocks = [
        (
            f"[{item.citation_id}]\n"
            f"Title: {item.chunk.title}\n"
            f"Page: {item.chunk.page_number}\n"
            f"Evidence: {item.chunk.text}"
        )
        for item in evidence
    ]
    context = "\n\n".join(context_blocks)
    return f"Question:\n{question}\n\nEvidence:\n{context}\n\nAnswer:"
