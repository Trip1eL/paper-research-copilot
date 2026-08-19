"""Versioned rubric and prompt construction for the answer LLM Judge."""

import json
from collections.abc import Mapping

from paper_research_copilot.evaluation.answer import AnswerCaseResult
from paper_research_copilot.evaluation.answer_datasets import AnswerEvaluationCase

JUDGE_PROMPT_VERSION = "answer_judge_v1"

JUDGE_SYSTEM_PROMPT = """You are an independent evaluator of academic RAG answers.
Evaluate the candidate answer; do not answer the research question yourself.
Use only the reference answer and the cited evidence supplied in the request.
Do not reward style, length, confidence, or matching wording by itself.

Score each dimension from 0 to 4:
- correctness: 4 fully correct and covers the reference; 3 mostly correct with a minor omission;
  2 partly correct or materially incomplete; 1 mostly incorrect; 0 no valid answer.
- faithfulness: 4 every material factual claim is entailed by its cited evidence; 3 one minor
  unsupported detail; 2 mixed supported and unsupported claims; 1 mostly unsupported; 0 no
  meaningful cited support.
- citation_completeness: 4 every externally verifiable material claim has sufficient citations;
  3 one minor claim lacks support; 2 several claims lack citations; 1 most claims lack citations;
  0 no usable citations.

For claim_assessments, include at most 8 material claims. A claim's verdict must be one of:
entailed, partially_entailed, unsupported. Citation IDs must come from the candidate answer.
Set needs_human_review=true for ambiguous evidence, conflicting sources, or uncertain scoring.
Return valid JSON only. Do not wrap it in Markdown."""


def build_judge_user_prompt(
    case: AnswerEvaluationCase,
    result: AnswerCaseResult,
    evidence_text_by_chunk_id: Mapping[str, str],
) -> str:
    evidence_by_chunk = {item.chunk_id: item for item in result.evidence}
    cited_evidence = []
    for citation in result.citations:
        evidence = evidence_by_chunk.get(citation.chunk_id)
        cited_evidence.append(
            {
                "citation_id": citation.citation_id,
                "paper_id": citation.paper_id,
                "page_number": citation.page_number,
                "title": evidence.title if evidence else None,
                "evidence": (
                    evidence.text
                    if evidence and evidence.text
                    else evidence_text_by_chunk_id.get(citation.chunk_id, "")
                ),
            }
        )
    payload = {
        "question": case.question,
        "reference_answer": case.reference_answer,
        "reference_key_points": [
            {"id": item.key_point_id, "description": item.description} for item in case.key_points
        ],
        "candidate_answer": result.answer_text,
        "cited_evidence": cited_evidence,
        "required_output": {
            "correctness": {"score": "integer 0-4", "rationale": "concise string"},
            "faithfulness": {"score": "integer 0-4", "rationale": "concise string"},
            "citation_completeness": {
                "score": "integer 0-4",
                "rationale": "concise string",
            },
            "claim_assessments": [
                {
                    "claim": "material factual claim",
                    "citation_ids": ["C1"],
                    "verdict": "entailed|partially_entailed|unsupported",
                    "rationale": "concise evidence-based reason",
                }
            ],
            "needs_human_review": "boolean",
            "review_reason": "string; empty when review is not needed",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
