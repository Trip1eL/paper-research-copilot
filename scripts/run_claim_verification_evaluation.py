"""Run a bounded live smoke evaluation for production Claim Verification."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.agent import LlmClaimVerifier
from paper_research_copilot.agent.verification import ClaimVerificationOutcome
from paper_research_copilot.config import PROJECT_ROOT, get_settings
from paper_research_copilot.domain import Answer, Citation, PaperChunk, RetrievedChunk
from paper_research_copilot.integrations import OpenAICompatibleChatProvider


class ClaimVerificationCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^CV-[0-9]{3}$")
    source_case_id: str = Field(pattern=r"^AE-[0-9]{3}$")
    expected_status: Literal["passed", "revised"]
    answer_override: str | None = None
    forbidden_text: tuple[str, ...] = ()
    rationale: str = Field(min_length=10)


class ClaimVerificationRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    fingerprint: str
    outcome: ClaimVerificationOutcome


class ClaimVerificationCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    source_case_id: str
    expected_status: str
    actual_status: str
    status_correct: bool
    forbidden_text_removed: bool
    final_answer_status: str
    claim_count: int = Field(ge=0)
    supported_claims: int = Field(ge=0)
    partially_supported_claims: int = Field(ge=0)
    unsupported_claims: int = Field(ge=0)
    needs_human_review: bool
    latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    strict_pass: bool


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "claim_verification_v1.jsonl",
    )
    parser.add_argument(
        "--source-results",
        type=Path,
        default=PROJECT_ROOT / "evals" / "results" / "answer_hybrid_rrf_v2.jsonl",
    )
    parser.add_argument("--baseline-id", default="claim_verification_live_v1")
    args = parser.parse_args()

    cases = _load_cases(args.dataset)
    source_records = _load_source_records(args.source_results)
    settings = get_settings()
    relay_url, relay_key = settings.require_relay_credentials()
    verifier = LlmClaimVerifier(
        OpenAICompatibleChatProvider(
            base_url=relay_url,
            api_key=relay_key,
            model=settings.gpt_model_name,
            max_tokens=settings.agent_claim_verifier_max_tokens,
        ),
        model=settings.gpt_model_name,
        retry_attempts=2,
    )
    cache_path = (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "claim_verification"
        / args.baseline_id
        / "runs.jsonl"
    )
    cache = _load_cache(cache_path)
    results: list[ClaimVerificationCaseResult] = []
    for index, case in enumerate(cases, 1):
        source = source_records.get(case.source_case_id)
        if source is None:
            raise ValueError(f"Missing source Answer result: {case.source_case_id}")
        answer, evidence = _build_input(case, source)
        fingerprint = _fingerprint(case, answer, evidence, verifier.model)
        cached = cache.get(case.case_id)
        if cached is not None:
            if cached.fingerprint != fingerprint:
                raise ValueError(
                    f"Cached fingerprint changed for {case.case_id}; use a new baseline ID"
                )
            run = cached
            source_label = "cache"
        else:
            run = ClaimVerificationRun(
                case_id=case.case_id,
                fingerprint=fingerprint,
                outcome=verifier.verify(str(source["question"]), answer, evidence),
            )
            cache[case.case_id] = run
            _write_cache(cache_path, cache.values())
            source_label = "live"
        result = _evaluate(case, run)
        results.append(result)
        print(
            f"[{index}/{len(cases)}] {case.case_id}: source={source_label}, "
            f"status={result.actual_status}, strict={result.strict_pass}"
        )

    json_path, markdown_path = _write_report(
        args.baseline_id,
        args.dataset,
        args.source_results,
        settings.gpt_model_name,
        results,
    )
    passed = sum(item.strict_pass for item in results)
    print(f"Strict Pass: {passed}/{len(results)}")
    print(f"Baseline JSON: {json_path}")
    print(f"Baseline report: {markdown_path}")
    return 0 if passed == len(results) else 1


def _load_cases(path: Path) -> tuple[ClaimVerificationCase, ...]:
    cases = tuple(
        ClaimVerificationCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Claim Verification dataset must not be empty")
    if len({item.case_id for item in cases}) != len(cases):
        raise ValueError("Claim Verification Case IDs must be unique")
    return cases


def _load_source_records(path: Path) -> dict[str, dict[str, object]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        str(item["case_id"]): item
        for item in records
        if isinstance(item, dict) and "case_id" in item
    }


def _build_input(
    case: ClaimVerificationCase,
    source: dict[str, object],
) -> tuple[Answer, tuple[RetrievedChunk, ...]]:
    question = str(source["question"])
    evidence_records = source.get("evidence")
    citation_records = source.get("citations")
    if not isinstance(evidence_records, list) or not isinstance(citation_records, list):
        raise ValueError(f"Source result is missing Evidence/Citations: {case.source_case_id}")
    evidence_by_id = {
        str(item["citation_id"]): item for item in evidence_records if isinstance(item, dict)
    }
    retrieved: list[RetrievedChunk] = []
    citations: list[Citation] = []
    for raw_citation in citation_records:
        if not isinstance(raw_citation, dict):
            continue
        citation_id = str(raw_citation["citation_id"])
        raw_evidence = evidence_by_id[citation_id]
        text = str(raw_evidence["text"])
        chunk_id = str(raw_evidence["chunk_id"])
        paper_id = str(raw_evidence["paper_id"])
        title = str(raw_evidence["title"])
        page_number = int(raw_evidence["page_number"])
        score = float(raw_evidence["score"])
        source_path = f"evals/source/{paper_id}.pdf"
        chunk = PaperChunk(
            chunk_id=chunk_id,
            document_sha256=hashlib.sha256(paper_id.encode()).hexdigest(),
            chunk_index=int(raw_evidence["rank"]) - 1,
            chunking_version="chunking_v1",
            paper_id=paper_id,
            title=title,
            source_path=source_path,
            page_number=page_number,
            char_start=0,
            char_end=len(text),
            text=text,
        )
        retrieved.append(RetrievedChunk(citation_id=citation_id, score=score, chunk=chunk))
        citations.append(
            Citation(
                citation_id=citation_id,
                chunk_id=chunk_id,
                paper_id=paper_id,
                title=title,
                source_path=source_path,
                page_number=page_number,
                excerpt=text,
                retrieval_score=score,
            )
        )
    answer = Answer(
        question=question,
        text=case.answer_override or str(source["answer_text"]),
        citations=tuple(citations),
    )
    return answer, tuple(retrieved)


def _fingerprint(
    case: ClaimVerificationCase,
    answer: Answer,
    evidence: tuple[RetrievedChunk, ...],
    model: str,
) -> str:
    payload = {
        "case": case.model_dump(mode="json"),
        "answer": answer.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "model": model,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _evaluate(
    case: ClaimVerificationCase,
    run: ClaimVerificationRun,
) -> ClaimVerificationCaseResult:
    verification = run.outcome.verification
    final_text = run.outcome.answer.text.casefold()
    forbidden_removed = all(item.casefold() not in final_text for item in case.forbidden_text)
    status_correct = verification.status == case.expected_status
    counts = {
        verdict: sum(item.verdict == verdict for item in verification.claims)
        for verdict in ("supported", "partially_supported", "unsupported")
    }
    return ClaimVerificationCaseResult(
        case_id=case.case_id,
        source_case_id=case.source_case_id,
        expected_status=case.expected_status,
        actual_status=verification.status,
        status_correct=status_correct,
        forbidden_text_removed=forbidden_removed,
        final_answer_status=run.outcome.answer.status,
        claim_count=len(verification.claims),
        supported_claims=counts["supported"],
        partially_supported_claims=counts["partially_supported"],
        unsupported_claims=counts["unsupported"],
        needs_human_review=verification.needs_human_review,
        latency_ms=verification.latency_ms,
        attempts=verification.attempts,
        input_tokens=verification.usage.input_tokens or 0,
        output_tokens=verification.usage.output_tokens or 0,
        strict_pass=status_correct and forbidden_removed,
    )


def _write_report(
    baseline_id: str,
    dataset_path: Path,
    source_path: Path,
    model: str,
    results: list[ClaimVerificationCaseResult],
) -> tuple[Path, Path]:
    baseline_dir = PROJECT_ROOT / "evals" / "baselines"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{baseline_id}.json"
    markdown_path = baseline_dir / f"{baseline_id}.md"
    summary = {
        "case_count": len(results),
        "strict_pass_rate": sum(item.strict_pass for item in results) / len(results),
        "status_accuracy": sum(item.status_correct for item in results) / len(results),
        "forbidden_text_removal_rate": sum(
            item.forbidden_text_removed for item in results
        )
        / len(results),
        "total_latency_ms": sum(item.latency_ms for item in results),
        "total_input_tokens": sum(item.input_tokens for item in results),
        "total_output_tokens": sum(item.output_tokens for item in results),
    }
    payload = {
        "config": {
            "baseline_id": baseline_id,
            "dataset_path": dataset_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "source_results_path": source_path.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "source_results_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "model": model,
        },
        "summary": summary,
        "cases": [item.model_dump(mode="json") for item in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Claim Verification Live Evaluation v1",
        "",
        f"- Case：{len(results)}",
        f"- Strict Pass：{summary['strict_pass_rate']:.2%}",
        f"- Status Accuracy：{summary['status_accuracy']:.2%}",
        f"- 注入内容移除率：{summary['forbidden_text_removal_rate']:.2%}",
        f"- 总 Verifier 延迟：{summary['total_latency_ms']:.0f} ms",
        f"- Token：{summary['total_input_tokens']:.0f} input / "
        f"{summary['total_output_tokens']:.0f} output",
        "",
        "| Case | Source | Expected | Actual | Claims S/P/U | Final | Latency | Strict |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item.case_id} | {item.source_case_id} | {item.expected_status} | "
            f"{item.actual_status} | {item.supported_claims}/"
            f"{item.partially_supported_claims}/{item.unsupported_claims} | "
            f"{item.final_answer_status} | {item.latency_ms:.0f} ms | "
            f"{'PASS' if item.strict_pass else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "该 Smoke 只验证两个历史真实回答和两个人工注入错误。它证明生产 Prompt 能执行预设的",
            "放行/修订控制，不等价于开放域 Claim Verification 的统计正确率，也不能消除单模型偏差。",
            "四条结果已人工检查：正样本内容未改变；两个对抗样本中的绝对成功率、错误年份和"
            "错误交互机制均从最终回答中移除。",
            "",
        ]
    )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, markdown_path


def _load_cache(path: Path) -> dict[str, ClaimVerificationRun]:
    if not path.is_file():
        return {}
    records = [
        ClaimVerificationRun.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {item.case_id: item for item in records}


def _write_cache(path: Path, records: Iterable[ClaimVerificationRun]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(item.model_dump_json() for item in sorted(records, key=lambda x: x.case_id))
    path.write_text(content + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
