"""Deterministic end-to-end answer and citation evaluation."""

import hashlib
import re
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import Answer, RetrievedChunk
from paper_research_copilot.evaluation.answer_datasets import AnswerEvaluationCase
from paper_research_copilot.reporting import AnswerGenerationTrace, AnswerGenerator
from paper_research_copilot.retrieval import CandidateRetriever

_CITATION_PATTERN = re.compile(r"\[C[1-9][0-9]*\]")
_CITATION_AFTER_PUNCTUATION = re.compile(r"([。！？!?.])\s*((?:\[C[1-9][0-9]*\])+)")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?])|(?<=\.)\s+|[\r\n]+")


class EvaluatedEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1)
    citation_id: str
    chunk_id: str
    paper_id: str | None
    page_number: int = Field(ge=1)
    score: float
    title: str
    text: str = ""


class EvaluatedCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    citation_id: str
    chunk_id: str
    paper_id: str | None
    page_number: int = Field(ge=1)


class AnswerCaseMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_succeeded: bool
    answerability_correct: bool
    key_point_recall: float | None = Field(default=None, ge=0, le=1)
    citation_paper_precision: float | None = Field(default=None, ge=0, le=1)
    citation_paper_recall: float | None = Field(default=None, ge=0, le=1)
    strict_page_precision: float | None = Field(default=None, ge=0, le=1)
    strict_page_recall: float | None = Field(default=None, ge=0, le=1)
    sentence_citation_coverage: float | None = Field(default=None, ge=0, le=1)


class AnswerCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    source_case_id: str | None
    question: str
    question_type: str
    difficulty: str
    answerable: bool
    retrieval_latency_ms: float = Field(ge=0)
    generation_latency_ms: float = Field(ge=0)
    total_latency_ms: float = Field(ge=0)
    answer_status: Literal["answered", "insufficient_evidence", "error"]
    answer_text: str
    error: str | None = None
    generation_trace: AnswerGenerationTrace | None = None
    matched_key_points: tuple[str, ...] = ()
    evidence: tuple[EvaluatedEvidence, ...]
    citations: tuple[EvaluatedCitation, ...]
    metrics: AnswerCaseMetrics


class AnswerEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_id: str
    corpus_version: int = Field(ge=1)
    collection_name: str
    retrieval_strategy: str
    retrieval_parameters: dict[str, str | int | float | bool]
    answer_model: str
    answer_prompt_version: str
    answer_retry_attempts: int = Field(ge=1)
    top_k: int = Field(ge=1)


class AnswerEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: AnswerEvaluationConfig
    case_count: int = Field(ge=1)
    answerable_count: int = Field(ge=0)
    unanswerable_count: int = Field(ge=0)
    generation_success_rate: float = Field(ge=0, le=1)
    answerability_accuracy: float = Field(ge=0, le=1)
    key_point_recall: float = Field(ge=0, le=1)
    citation_paper_precision: float = Field(ge=0, le=1)
    citation_paper_recall: float = Field(ge=0, le=1)
    strict_page_precision: float = Field(ge=0, le=1)
    strict_page_recall: float = Field(ge=0, le=1)
    sentence_citation_coverage: float = Field(ge=0, le=1)
    empty_response_case_rate: float = Field(default=0, ge=0, le=1)
    truncation_case_rate: float = Field(default=0, ge=0, le=1)
    retry_trigger_rate: float = Field(default=0, ge=0, le=1)
    retry_recovery_rate: float = Field(default=0, ge=0, le=1)
    finish_reason_counts: dict[str, int] = Field(default_factory=dict)
    mean_total_latency_ms: float = Field(ge=0)
    p50_total_latency_ms: float = Field(ge=0)
    p95_total_latency_ms: float = Field(ge=0)
    failed_cases: tuple[str, ...]
    answerability_errors: tuple[str, ...]


def run_answer_evaluation(
    retriever: CandidateRetriever,
    answer_generator: AnswerGenerator,
    cases: Sequence[AnswerEvaluationCase],
    *,
    top_k: int,
    progress: Callable[[AnswerCaseResult, int, int], None] | None = None,
) -> tuple[AnswerCaseResult, ...]:
    if top_k < 1:
        raise ValueError("Top-K must be at least 1")
    results: list[AnswerCaseResult] = []
    for index, case in enumerate(cases, start=1):
        retrieval_started = time.perf_counter()
        evidence: tuple[RetrievedChunk, ...] = ()
        answer: Answer | None = None
        error: str | None = None
        generation_trace: AnswerGenerationTrace | None = None
        try:
            evidence = retriever.retrieve(case.question, top_k)
        except Exception as exc:  # Evaluation must record a failed case and continue.
            error = f"retrieval:{type(exc).__name__}: {exc}"
        retrieval_latency_ms = (time.perf_counter() - retrieval_started) * 1000

        generation_started = time.perf_counter()
        if error is None:
            try:
                answer = answer_generator.generate(case.question, evidence)
            except Exception as exc:  # Evaluation must expose invalid model outputs.
                error = f"generation:{type(exc).__name__}: {exc}"
            try:
                generation_trace = answer_generator.trace_for(case.question)
            except LookupError:
                generation_trace = None
        generation_latency_ms = (time.perf_counter() - generation_started) * 1000
        result = build_answer_case_result(
            case,
            evidence,
            answer,
            error,
            generation_trace,
            retrieval_latency_ms,
            generation_latency_ms,
        )
        results.append(result)
        if progress:
            progress(result, index, len(cases))
    return tuple(results)


def build_answer_case_result(
    case: AnswerEvaluationCase,
    evidence: Sequence[RetrievedChunk],
    answer: Answer | None,
    error: str | None,
    generation_trace: AnswerGenerationTrace | None,
    retrieval_latency_ms: float,
    generation_latency_ms: float,
) -> AnswerCaseResult:
    answer_text = answer.text if answer else ""
    status: Literal["answered", "insufficient_evidence", "error"] = (
        answer.status if answer else "error"
    )
    matched_key_points = tuple(
        key_point.key_point_id
        for key_point in case.key_points
        if any(alias.casefold() in answer_text.casefold() for alias in key_point.match_any)
    )
    citations = tuple(
        EvaluatedCitation(
            citation_id=citation.citation_id,
            chunk_id=citation.chunk_id,
            paper_id=citation.paper_id,
            page_number=citation.page_number,
        )
        for citation in (answer.citations if answer else ())
    )
    metrics = _case_metrics(case, status, answer_text, citations, matched_key_points, error)
    return AnswerCaseResult(
        case_id=case.case_id,
        source_case_id=case.source_case_id,
        question=case.question,
        question_type=case.question_type,
        difficulty=case.difficulty,
        answerable=case.answerable,
        retrieval_latency_ms=round(retrieval_latency_ms, 2),
        generation_latency_ms=round(generation_latency_ms, 2),
        total_latency_ms=round(retrieval_latency_ms + generation_latency_ms, 2),
        answer_status=status,
        answer_text=answer_text,
        error=error,
        generation_trace=generation_trace,
        matched_key_points=matched_key_points,
        evidence=tuple(
            EvaluatedEvidence(
                rank=rank,
                citation_id=item.citation_id,
                chunk_id=item.chunk.chunk_id,
                paper_id=item.chunk.paper_id,
                page_number=item.chunk.page_number,
                score=item.score,
                title=item.chunk.title,
                text=item.chunk.text,
            )
            for rank, item in enumerate(evidence, start=1)
        ),
        citations=citations,
        metrics=metrics,
    )


def _case_metrics(
    case: AnswerEvaluationCase,
    status: str,
    answer_text: str,
    citations: Sequence[EvaluatedCitation],
    matched_key_points: Sequence[str],
    error: str | None,
) -> AnswerCaseMetrics:
    succeeded = error is None
    answerability_correct = succeeded and (
        (case.answerable and status == "answered")
        or (not case.answerable and status == "insufficient_evidence")
    )
    if not case.answerable:
        return AnswerCaseMetrics(
            generation_succeeded=succeeded,
            answerability_correct=answerability_correct,
        )

    gold_papers = {item.paper_id for item in case.relevant}
    cited_papers = {item.paper_id for item in citations if item.paper_id is not None}
    strict_citations = [
        citation
        for citation in citations
        if any(
            citation.paper_id == relevant.paper_id and citation.page_number in relevant.pages
            for relevant in case.relevant
        )
    ]
    strict_covered_papers = {
        relevant.paper_id
        for relevant in case.relevant
        if any(
            citation.paper_id == relevant.paper_id and citation.page_number in relevant.pages
            for citation in citations
        )
    }
    return AnswerCaseMetrics(
        generation_succeeded=succeeded,
        answerability_correct=answerability_correct,
        key_point_recall=len(matched_key_points) / len(case.key_points),
        citation_paper_precision=(
            len(cited_papers & gold_papers) / len(cited_papers) if cited_papers else 0
        ),
        citation_paper_recall=len(cited_papers & gold_papers) / len(gold_papers),
        strict_page_precision=len(strict_citations) / len(citations) if citations else 0,
        strict_page_recall=len(strict_covered_papers) / len(gold_papers),
        sentence_citation_coverage=_sentence_citation_coverage(answer_text),
    )


def _sentence_citation_coverage(answer_text: str) -> float:
    normalized = _CITATION_AFTER_PUNCTUATION.sub(r"\2\1 ", answer_text)
    sentences = [
        sentence.strip(" -#*\t")
        for sentence in _SENTENCE_BOUNDARY.split(normalized)
        if sentence.strip(" -#*\t")
    ]
    if not sentences:
        return 0
    return sum(bool(_CITATION_PATTERN.search(sentence)) for sentence in sentences) / len(sentences)


def build_answer_evaluation_report(
    results: Sequence[AnswerCaseResult],
    config: AnswerEvaluationConfig,
) -> AnswerEvaluationReport:
    if not results:
        raise ValueError("Cannot build an answer report without case results")
    answerable = [result for result in results if result.answerable]
    latencies = [result.total_latency_ms for result in results]
    traces = [result.generation_trace for result in results if result.generation_trace]
    retry_traces = [trace for trace in traces if trace.retry_triggered]
    finish_reason_counts: dict[str, int] = {}
    for trace in traces:
        for attempt in trace.attempts:
            finish_reason_counts[attempt.finish_reason] = (
                finish_reason_counts.get(attempt.finish_reason, 0) + 1
            )
    return AnswerEvaluationReport(
        config=config,
        case_count=len(results),
        answerable_count=len(answerable),
        unanswerable_count=len(results) - len(answerable),
        generation_success_rate=_mean(
            float(result.metrics.generation_succeeded) for result in results
        ),
        answerability_accuracy=_mean(
            float(result.metrics.answerability_correct) for result in results
        ),
        key_point_recall=_mean_metric(answerable, "key_point_recall"),
        citation_paper_precision=_mean_metric(answerable, "citation_paper_precision"),
        citation_paper_recall=_mean_metric(answerable, "citation_paper_recall"),
        strict_page_precision=_mean_metric(answerable, "strict_page_precision"),
        strict_page_recall=_mean_metric(answerable, "strict_page_recall"),
        sentence_citation_coverage=_mean_metric(answerable, "sentence_citation_coverage"),
        empty_response_case_rate=_mean(
            float(
                result.generation_trace is not None
                and any(attempt.outcome == "empty" for attempt in result.generation_trace.attempts)
            )
            for result in results
        ),
        truncation_case_rate=_mean(
            float(
                result.generation_trace is not None
                and any(
                    attempt.outcome == "truncated" for attempt in result.generation_trace.attempts
                )
            )
            for result in results
        ),
        retry_trigger_rate=len(retry_traces) / len(results),
        retry_recovery_rate=(
            _mean(float(trace.retry_recovered) for trace in retry_traces) if retry_traces else 0
        ),
        finish_reason_counts=finish_reason_counts,
        mean_total_latency_ms=round(_mean(latencies), 2),
        p50_total_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_total_latency_ms=round(_percentile(latencies, 0.95), 2),
        failed_cases=tuple(
            result.case_id for result in results if not result.metrics.generation_succeeded
        ),
        answerability_errors=tuple(
            result.case_id for result in results if not result.metrics.answerability_correct
        ),
    )


def build_answer_evaluation_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    corpus_id: str,
    corpus_version: int,
    collection_name: str,
    retrieval_strategy: str,
    retrieval_parameters: dict[str, str | int | float | bool],
    answer_model: str,
    answer_prompt_version: str,
    answer_retry_attempts: int,
    top_k: int,
    project_root: Path,
) -> AnswerEvaluationConfig:
    return AnswerEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=dataset_path.resolve().relative_to(project_root.resolve()).as_posix(),
        dataset_sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        corpus_id=corpus_id,
        corpus_version=corpus_version,
        collection_name=collection_name,
        retrieval_strategy=retrieval_strategy,
        retrieval_parameters=retrieval_parameters,
        answer_model=answer_model,
        answer_prompt_version=answer_prompt_version,
        answer_retry_attempts=answer_retry_attempts,
        top_k=top_k,
    )


def write_answer_evaluation_artifacts(
    report: AnswerEvaluationReport,
    results: Sequence[AnswerCaseResult],
    *,
    baseline_dir: Path,
    results_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    raw_path = results_dir / f"{report.config.baseline_id}.jsonl"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    raw_path.write_text(
        "\n".join(result.model_dump_json() for result in results) + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path, raw_path


def _markdown_report(
    report: AnswerEvaluationReport,
    results: Sequence[AnswerCaseResult],
) -> str:
    lines = [
        f"# Answer Baseline: {report.config.baseline_id}",
        "",
        f"- Dataset：`{report.config.dataset_path}`（{report.case_count} cases）",
        f"- Retrieval：`{report.config.retrieval_strategy}` / Top-{report.config.top_k}",
        f"- Answer model：`{report.config.answer_model}`",
        f"- Prompt version：`{report.config.answer_prompt_version}`",
        f"- Empty-answer retry attempts：`{report.config.answer_retry_attempts}`",
        "",
        "## 总体指标",
        "",
        "| Generation Success | Answerability | Key Point Recall | Citation Paper P/R | "
        "Strict Page P/R | Sentence Citation | P50/P95 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.generation_success_rate:.2%} | {report.answerability_accuracy:.2%} | "
        f"{report.key_point_recall:.2%} | {report.citation_paper_precision:.2%} / "
        f"{report.citation_paper_recall:.2%} | {report.strict_page_precision:.2%} / "
        f"{report.strict_page_recall:.2%} | {report.sentence_citation_coverage:.2%} | "
        f"{report.p50_total_latency_ms:.0f} / {report.p95_total_latency_ms:.0f} ms |",
        "",
        "## 逐题结果",
        "",
        "| Case | Type | Status | Key Points | Paper Recall | Strict Page Recall | "
        "Sentence Citation | Total Latency |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        metrics = result.metrics
        lines.append(
            f"| {result.case_id} | {result.question_type} | {result.answer_status} | "
            f"{_format_optional(metrics.key_point_recall)} | "
            f"{_format_optional(metrics.citation_paper_recall)} | "
            f"{_format_optional(metrics.strict_page_recall)} | "
            f"{_format_optional(metrics.sentence_citation_coverage)} | "
            f"{result.total_latency_ms:.0f} ms |"
        )
    lines.extend(
        [
            "",
            "## 失败 Case",
            "",
            f"- Generation failure：{', '.join(report.failed_cases) or '无'}",
            f"- Answerability error：{', '.join(report.answerability_errors) or '无'}",
            f"- Empty response cases：{report.empty_response_case_rate:.2%}",
            f"- Truncation cases：{report.truncation_case_rate:.2%}",
            f"- Retry trigger / recovery：{report.retry_trigger_rate:.2%} / "
            f"{report.retry_recovery_rate:.2%}",
            f"- Finish reasons：{report.finish_reason_counts}",
            "",
            "## 口径限制",
            "",
            "- Key Point Recall 是人工别名匹配，只衡量关键术语覆盖，不等于语义正确性。",
            "- Strict Page 指标使用非穷举人工页码，因此是严格下界。",
            "- Sentence Citation 只检查句子是否含 Citation marker，不判断 "
            "Claim-Evidence entailment。",
            "- 下一阶段使用独立 LLM Judge 补充 correctness 与 faithfulness，"
            "不能替代这些确定性指标。",
        ]
    )
    return "\n".join(lines) + "\n"


def _mean_metric(results: Sequence[AnswerCaseResult], field: str) -> float:
    values = [getattr(result.metrics, field) for result in results]
    return _mean(value for value in values if value is not None)


def _mean(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else 0


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, round((len(ordered) - 1) * percentile))]


def _format_optional(value: float | None) -> str:
    return "-" if value is None else f"{value:.2%}"
