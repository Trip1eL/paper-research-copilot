"""Deterministic Open-world evaluation contracts, metrics, and artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_research_copilot.agent import AgentResult

OpenWorldCategory = Literal["in_corpus", "recoverable", "unrecoverable", "ambiguous"]
AcquisitionExpectation = Literal["forbidden", "required", "optional"]
ExpectedAnswerStatus = Literal["answered", "insufficient_evidence"]

_CATEGORY_PREFIX = {
    "in_corpus": "IC",
    "recoverable": "RC",
    "unrecoverable": "UR",
    "ambiguous": "AM",
}


class OpenWorldEvaluationCase(BaseModel):
    """Human-reviewed expected behavior for one clean Dynamic Corpus run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^OW-(?:IC|RC|UR|AM)-[0-9]{3}$")
    category: OpenWorldCategory
    question: str = Field(min_length=5)
    acquisition_expectation: AcquisitionExpectation
    expected_answer_status: ExpectedAnswerStatus
    target_arxiv_ids: tuple[str, ...] = ()
    expected_curated_paper_ids: tuple[str, ...] = ()
    rationale: str = Field(min_length=10)

    @model_validator(mode="after")
    def validate_contract(self) -> OpenWorldEvaluationCase:
        if not self.case_id.startswith(f"OW-{_CATEGORY_PREFIX[self.category]}-"):
            raise ValueError("Open-world Case ID prefix must agree with category")
        if self.category == "in_corpus":
            if self.acquisition_expectation != "forbidden":
                raise ValueError("In-corpus cases must forbid Acquisition")
            if self.expected_answer_status != "answered":
                raise ValueError("In-corpus cases must expect an answer")
            if not self.expected_curated_paper_ids:
                raise ValueError("In-corpus cases require expected Curated paper IDs")
        elif self.category == "recoverable":
            if self.acquisition_expectation != "required":
                raise ValueError("Recoverable cases must require Acquisition")
            if self.expected_answer_status != "answered":
                raise ValueError("Recoverable cases must expect an answer")
            if not self.target_arxiv_ids:
                raise ValueError("Recoverable cases require target arXiv IDs")
        elif self.expected_answer_status != "insufficient_evidence":
            raise ValueError("Unrecoverable and ambiguous cases must expect refusal")
        if self.category != "recoverable" and self.target_arxiv_ids:
            raise ValueError("Only recoverable cases may declare target arXiv IDs")
        return self


class OpenWorldCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: OpenWorldCategory
    question: str
    run_succeeded: bool
    error: str | None = None
    acquisition_expectation: AcquisitionExpectation
    acquisition_triggered: bool
    acquisition_correct: bool
    acquisition_rounds: int = Field(ge=0)
    bounded_acquisition: bool
    acquisition_status: str | None = None
    acquisition_query: str | None = None
    downloaded_count: int = Field(ge=0)
    indexed_count: int = Field(ge=0)
    answer_status: ExpectedAnswerStatus | Literal["error"]
    answer_behavior_correct: bool
    evidence_count: int = Field(ge=0)
    dynamic_evidence_count: int = Field(ge=0)
    dynamic_evidence_rate: float = Field(ge=0, le=1)
    target_dynamic_evidence_hit: bool | None = None
    target_citation_hit: bool | None = None
    expected_curated_citation_hit: bool | None = None
    dynamic_parser_provenance_valid: bool | None = None
    citation_validation_passed: bool
    strict_pass: bool
    points_before: int = Field(ge=0)
    points_after: int = Field(ge=0)
    point_delta: int
    elapsed_ms: float = Field(ge=0)
    acquisition_latency_ms: float = Field(ge=0)
    known_input_tokens: int = Field(ge=0)
    known_output_tokens: int = Field(ge=0)
    retrieved_dynamic_arxiv_ids: tuple[str, ...] = ()
    cited_arxiv_ids: tuple[str, ...] = ()
    trace_nodes: tuple[str, ...] = ()


class OpenWorldCategorySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: OpenWorldCategory
    case_count: int = Field(ge=1)
    strict_pass_rate: float = Field(ge=0, le=1)
    acquisition_rate: float = Field(ge=0, le=1)
    answer_behavior_accuracy: float = Field(ge=0, le=1)
    p50_elapsed_ms: float = Field(ge=0)
    p95_elapsed_ms: float = Field(ge=0)


class OpenWorldSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_count: int = Field(ge=1)
    run_success_rate: float = Field(ge=0, le=1)
    strict_pass_rate: float = Field(ge=0, le=1)
    acquisition_trigger_precision: float | None = Field(default=None, ge=0, le=1)
    acquisition_trigger_recall: float | None = Field(default=None, ge=0, le=1)
    in_corpus_false_trigger_rate: float | None = Field(default=None, ge=0, le=1)
    recoverable_success_rate: float | None = Field(default=None, ge=0, le=1)
    unrecoverable_abstention_rate: float | None = Field(default=None, ge=0, le=1)
    unrecoverable_no_index_rate: float | None = Field(default=None, ge=0, le=1)
    ambiguous_abstention_rate: float | None = Field(default=None, ge=0, le=1)
    dynamic_evidence_hit_rate: float | None = Field(default=None, ge=0, le=1)
    target_citation_hit_rate: float | None = Field(default=None, ge=0, le=1)
    dynamic_parser_provenance_rate: float | None = Field(default=None, ge=0, le=1)
    bounded_acquisition_rate: float = Field(ge=0, le=1)
    answer_behavior_accuracy: float = Field(ge=0, le=1)
    in_corpus_dynamic_evidence_rate: float | None = Field(default=None, ge=0, le=1)
    p50_elapsed_ms: float = Field(ge=0)
    p95_elapsed_ms: float = Field(ge=0)
    total_downloaded: int = Field(ge=0)
    total_indexed: int = Field(ge=0)
    total_point_delta: int
    known_input_tokens: int = Field(ge=0)
    known_output_tokens: int = Field(ge=0)


class OpenWorldEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str = Field(min_length=3)
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: tuple[str, ...] = Field(min_length=1)
    corpus_version: int = Field(ge=1)
    curated_collection: str
    dynamic_state_policy: Literal["isolated_empty_per_case"]
    planner_model: str
    answer_model: str
    max_retries: int = Field(ge=0, le=1)
    max_acquisition_rounds: int = Field(ge=0, le=1)
    notes: tuple[str, ...] = ()


class OpenWorldEvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: OpenWorldEvaluationConfig
    summary: OpenWorldSummary
    categories: tuple[OpenWorldCategorySummary, ...]


def load_open_world_cases(path: Path) -> tuple[OpenWorldEvaluationCase, ...]:
    cases = tuple(
        OpenWorldEvaluationCase.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("Open-world evaluation dataset is empty")
    case_ids = [case.case_id for case in cases]
    questions = [" ".join(case.question.casefold().split()) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Open-world dataset contains duplicate Case IDs")
    if len(questions) != len(set(questions)):
        raise ValueError("Open-world dataset contains duplicate questions")
    return cases


def evaluate_open_world_case(
    case: OpenWorldEvaluationCase,
    result: AgentResult | None,
    *,
    elapsed_ms: float,
    points_before: int,
    points_after: int,
    error: str | None = None,
) -> OpenWorldCaseResult:
    if (result is None) == (error is None):
        raise ValueError("Open-world observation requires exactly one Agent result or error")
    if result is None:
        return _error_result(
            case,
            error=error or "Unknown error",
            elapsed_ms=elapsed_ms,
            points_before=points_before,
            points_after=points_after,
        )

    acquisition_triggered = result.acquisition_rounds > 0
    acquisition_correct = _acquisition_correct(case, acquisition_triggered)
    answer_correct = result.answer.status == case.expected_answer_status
    evidence_by_chunk_id = {item.chunk.chunk_id: item.chunk for item in result.evidence}
    cited_chunks = tuple(
        evidence_by_chunk_id[citation.chunk_id]
        for citation in result.answer.citations
        if citation.chunk_id in evidence_by_chunk_id
    )
    dynamic_evidence = tuple(
        item.chunk for item in result.evidence if item.chunk.corpus_id == "paper-dynamic"
    )
    target_ids = set(case.target_arxiv_ids)
    target_evidence_hit = (
        any(chunk.arxiv_id in target_ids for chunk in dynamic_evidence)
        if target_ids
        else None
    )
    target_citation_hit = (
        any(chunk.arxiv_id in target_ids for chunk in cited_chunks)
        if target_ids
        else None
    )
    target_dynamic_chunks = tuple(
        chunk for chunk in dynamic_evidence if chunk.arxiv_id in target_ids
    )
    parser_provenance_valid = (
        bool(target_dynamic_chunks)
        and all(
            chunk.parser_name
            and chunk.parser_version != "unversioned"
            and chunk.source_path.casefold().endswith(".pdf")
            for chunk in target_dynamic_chunks
        )
        if target_ids
        else None
    )
    curated_ids = set(case.expected_curated_paper_ids)
    curated_citation_hit = (
        any(chunk.paper_id in curated_ids for chunk in cited_chunks)
        if curated_ids
        else None
    )
    citation_validation = any(
        event.node == "validate_citations" and event.outcome == "valid"
        for event in result.trace
    )
    bounded = result.acquisition_rounds <= 1
    strict_pass = _strict_pass(
        case,
        acquisition_correct=acquisition_correct,
        answer_correct=answer_correct,
        bounded=bounded,
        citation_validation=citation_validation,
        target_evidence_hit=target_evidence_hit,
        target_citation_hit=target_citation_hit,
        curated_citation_hit=curated_citation_hit,
        parser_provenance_valid=parser_provenance_valid,
        no_dynamic_writes=points_after == points_before,
    )
    acquisition_events = [event for event in result.trace if event.node == "acquire_evidence"]
    input_tokens, output_tokens = _known_tokens(result)
    evidence_count = len(result.evidence)
    acquisition = result.acquisition
    return OpenWorldCaseResult(
        case_id=case.case_id,
        category=case.category,
        question=case.question,
        run_succeeded=True,
        acquisition_expectation=case.acquisition_expectation,
        acquisition_triggered=acquisition_triggered,
        acquisition_correct=acquisition_correct,
        acquisition_rounds=result.acquisition_rounds,
        bounded_acquisition=bounded,
        acquisition_status=acquisition.status if acquisition else None,
        acquisition_query=acquisition.query if acquisition else None,
        downloaded_count=acquisition.downloaded_count if acquisition else 0,
        indexed_count=acquisition.indexed_count if acquisition else 0,
        answer_status=result.answer.status,
        answer_behavior_correct=answer_correct,
        evidence_count=evidence_count,
        dynamic_evidence_count=len(dynamic_evidence),
        dynamic_evidence_rate=(len(dynamic_evidence) / evidence_count if evidence_count else 0),
        target_dynamic_evidence_hit=target_evidence_hit,
        target_citation_hit=target_citation_hit,
        expected_curated_citation_hit=curated_citation_hit,
        dynamic_parser_provenance_valid=parser_provenance_valid,
        citation_validation_passed=citation_validation,
        strict_pass=strict_pass,
        points_before=points_before,
        points_after=points_after,
        point_delta=points_after - points_before,
        elapsed_ms=elapsed_ms,
        acquisition_latency_ms=sum(event.latency_ms for event in acquisition_events),
        known_input_tokens=input_tokens,
        known_output_tokens=output_tokens,
        retrieved_dynamic_arxiv_ids=tuple(
            sorted({chunk.arxiv_id for chunk in dynamic_evidence if chunk.arxiv_id})
        ),
        cited_arxiv_ids=tuple(
            sorted({chunk.arxiv_id for chunk in cited_chunks if chunk.arxiv_id})
        ),
        trace_nodes=tuple(event.node for event in result.trace),
    )


def build_open_world_report(
    results: Sequence[OpenWorldCaseResult],
    config: OpenWorldEvaluationConfig,
) -> OpenWorldEvaluationReport:
    if not results:
        raise ValueError("Cannot build an Open-world report without results")
    if len(results) != len(config.case_ids) or {item.case_id for item in results} != set(
        config.case_ids
    ):
        raise ValueError("Open-world results must exactly match configured Case IDs")
    grouped: defaultdict[OpenWorldCategory, list[OpenWorldCaseResult]] = defaultdict(list)
    for result in results:
        grouped[result.category].append(result)
    categories = tuple(
        _category_summary(category, samples) for category, samples in grouped.items()
    )
    return OpenWorldEvaluationReport(
        config=config,
        summary=_overall_summary(results),
        categories=categories,
    )


def build_open_world_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    cases: Sequence[OpenWorldEvaluationCase],
    corpus_version: int,
    curated_collection: str,
    planner_model: str,
    answer_model: str,
    max_retries: int,
    max_acquisition_rounds: int,
    project_root: Path,
    notes: Sequence[str] = (),
) -> OpenWorldEvaluationConfig:
    resolved = dataset_path.resolve()
    try:
        display_path = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved)
    return OpenWorldEvaluationConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=display_path,
        dataset_sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        case_ids=tuple(case.case_id for case in cases),
        corpus_version=corpus_version,
        curated_collection=curated_collection,
        dynamic_state_policy="isolated_empty_per_case",
        planner_model=planner_model,
        answer_model=answer_model,
        max_retries=max_retries,
        max_acquisition_rounds=max_acquisition_rounds,
        notes=tuple(notes),
    )


def write_open_world_artifacts(
    report: OpenWorldEvaluationReport,
    results: Sequence[OpenWorldCaseResult],
    *,
    baseline_dir: Path,
    diagnostics_dir: Path,
) -> tuple[Path, Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    diagnostics_path = diagnostics_dir / f"{report.config.baseline_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report, results), encoding="utf-8")
    diagnostics_path.write_text(
        json.dumps(
            [result.model_dump(mode="json") for result in results],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path, diagnostics_path


def _error_result(
    case: OpenWorldEvaluationCase,
    *,
    error: str,
    elapsed_ms: float,
    points_before: int,
    points_after: int,
) -> OpenWorldCaseResult:
    return OpenWorldCaseResult(
        case_id=case.case_id,
        category=case.category,
        question=case.question,
        run_succeeded=False,
        error=error,
        acquisition_expectation=case.acquisition_expectation,
        acquisition_triggered=False,
        acquisition_correct=False,
        acquisition_rounds=0,
        bounded_acquisition=True,
        downloaded_count=0,
        indexed_count=0,
        answer_status="error",
        answer_behavior_correct=False,
        evidence_count=0,
        dynamic_evidence_count=0,
        dynamic_evidence_rate=0,
        citation_validation_passed=False,
        strict_pass=False,
        points_before=points_before,
        points_after=points_after,
        point_delta=points_after - points_before,
        elapsed_ms=elapsed_ms,
        acquisition_latency_ms=0,
        known_input_tokens=0,
        known_output_tokens=0,
    )


def _acquisition_correct(case: OpenWorldEvaluationCase, triggered: bool) -> bool:
    if case.acquisition_expectation == "required":
        return triggered
    if case.acquisition_expectation == "forbidden":
        return not triggered
    return True


def _strict_pass(
    case: OpenWorldEvaluationCase,
    *,
    acquisition_correct: bool,
    answer_correct: bool,
    bounded: bool,
    citation_validation: bool,
    target_evidence_hit: bool | None,
    target_citation_hit: bool | None,
    curated_citation_hit: bool | None,
    parser_provenance_valid: bool | None,
    no_dynamic_writes: bool,
) -> bool:
    base = acquisition_correct and answer_correct and bounded and citation_validation
    if case.category == "recoverable":
        return (
            base
            and target_evidence_hit is True
            and target_citation_hit is True
            and parser_provenance_valid is True
        )
    if case.category == "in_corpus":
        return base and curated_citation_hit is True
    if case.category == "unrecoverable":
        return base and no_dynamic_writes
    return base


def _known_tokens(result: AgentResult) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for event in result.trace:
        for key, value in event.details.items():
            if not isinstance(value, int):
                continue
            if key.endswith("_input_tokens"):
                input_tokens += value
            elif key.endswith("_output_tokens"):
                output_tokens += value
    return input_tokens, output_tokens


def _category_summary(
    category: OpenWorldCategory,
    samples: Sequence[OpenWorldCaseResult],
) -> OpenWorldCategorySummary:
    return OpenWorldCategorySummary(
        category=category,
        case_count=len(samples),
        strict_pass_rate=_mean(item.strict_pass for item in samples),
        acquisition_rate=_mean(item.acquisition_triggered for item in samples),
        answer_behavior_accuracy=_mean(item.answer_behavior_correct for item in samples),
        p50_elapsed_ms=round(_percentile([item.elapsed_ms for item in samples], 0.50), 2),
        p95_elapsed_ms=round(_percentile([item.elapsed_ms for item in samples], 0.95), 2),
    )


def _overall_summary(samples: Sequence[OpenWorldCaseResult]) -> OpenWorldSummary:
    recoverable = [item for item in samples if item.category == "recoverable"]
    in_corpus = [item for item in samples if item.category == "in_corpus"]
    unrecoverable = [item for item in samples if item.category == "unrecoverable"]
    ambiguous = [item for item in samples if item.category == "ambiguous"]
    triggered = [item for item in samples if item.acquisition_triggered]
    in_corpus_evidence_count = sum(item.evidence_count for item in in_corpus)
    return OpenWorldSummary(
        case_count=len(samples),
        run_success_rate=_mean(item.run_succeeded for item in samples),
        strict_pass_rate=_mean(item.strict_pass for item in samples),
        acquisition_trigger_precision=_mean_optional(
            item.category == "recoverable" for item in triggered
        ),
        acquisition_trigger_recall=_mean_optional(
            item.acquisition_triggered for item in recoverable
        ),
        in_corpus_false_trigger_rate=_mean_optional(
            item.acquisition_triggered for item in in_corpus
        ),
        recoverable_success_rate=_mean_optional(item.strict_pass for item in recoverable),
        unrecoverable_abstention_rate=_mean_optional(
            item.answer_status == "insufficient_evidence" for item in unrecoverable
        ),
        unrecoverable_no_index_rate=_mean_optional(
            item.point_delta == 0 for item in unrecoverable
        ),
        ambiguous_abstention_rate=_mean_optional(
            item.answer_status == "insufficient_evidence" for item in ambiguous
        ),
        dynamic_evidence_hit_rate=_mean_optional(
            item.target_dynamic_evidence_hit is True for item in recoverable
        ),
        target_citation_hit_rate=_mean_optional(
            item.target_citation_hit is True for item in recoverable
        ),
        dynamic_parser_provenance_rate=_mean_optional(
            item.dynamic_parser_provenance_valid is True for item in recoverable
        ),
        bounded_acquisition_rate=_mean(item.bounded_acquisition for item in samples),
        answer_behavior_accuracy=_mean(item.answer_behavior_correct for item in samples),
        in_corpus_dynamic_evidence_rate=(
            round(
                sum(item.dynamic_evidence_count for item in in_corpus)
                / in_corpus_evidence_count,
                4,
            )
            if in_corpus_evidence_count
            else None
        ),
        p50_elapsed_ms=round(_percentile([item.elapsed_ms for item in samples], 0.50), 2),
        p95_elapsed_ms=round(_percentile([item.elapsed_ms for item in samples], 0.95), 2),
        total_downloaded=sum(item.downloaded_count for item in samples),
        total_indexed=sum(item.indexed_count for item in samples),
        total_point_delta=sum(item.point_delta for item in samples),
        known_input_tokens=sum(item.known_input_tokens for item in samples),
        known_output_tokens=sum(item.known_output_tokens for item in samples),
    )


def _mean(values: Iterable[bool]) -> float:
    materialized = tuple(values)
    if not materialized:
        raise ValueError("Mean requires at least one value")
    return sum(materialized) / len(materialized)


def _mean_optional(values: Iterable[bool]) -> float | None:
    materialized = tuple(values)
    return sum(materialized) / len(materialized) if materialized else None


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _markdown_report(
    report: OpenWorldEvaluationReport,
    results: Sequence[OpenWorldCaseResult],
) -> str:
    summary = report.summary
    lines = [
        f"# Open-world Evaluation：{report.config.baseline_id}",
        "",
        f"- Dataset：`{report.config.dataset_path}`（{summary.case_count} Cases）",
        f"- Curated Collection：`{report.config.curated_collection}`",
        "- Dynamic State：每个 Case 使用独立且初始为空的 Qdrant、SQLite 与 PDF 目录",
        f"- Planner / Answer：`{report.config.planner_model}` / `{report.config.answer_model}`",
        "",
        "## 总体指标",
        "",
        "| Strict Pass | Trigger Precision | Trigger Recall | In-corpus False Trigger | "
        "Recoverable Success | Unrecoverable Abstention | Unrecoverable No-index | "
        "Ambiguous Abstention |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        f"{summary.strict_pass_rate:.2%} | "
        f"{_optional_rate(summary.acquisition_trigger_precision)} | "
        f"{_optional_rate(summary.acquisition_trigger_recall)} | "
        f"{_optional_rate(summary.in_corpus_false_trigger_rate)} | "
        f"{_optional_rate(summary.recoverable_success_rate)} | "
        f"{_optional_rate(summary.unrecoverable_abstention_rate)} | "
        f"{_optional_rate(summary.unrecoverable_no_index_rate)} | "
        f"{_optional_rate(summary.ambiguous_abstention_rate)} |",
        "",
        "| Dynamic Evidence Hit | Target Citation Hit | Parser Provenance | Bounded Acquisition | "
        "Answer Behavior | In-corpus Dynamic Evidence | P50 / P95 | "
        "Downloaded / Indexed | Point Delta |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        f"{_optional_rate(summary.dynamic_evidence_hit_rate)} | "
        f"{_optional_rate(summary.target_citation_hit_rate)} | "
        f"{_optional_rate(summary.dynamic_parser_provenance_rate)} | "
        f"{summary.bounded_acquisition_rate:.2%} | "
        f"{summary.answer_behavior_accuracy:.2%} | "
        f"{_optional_rate(summary.in_corpus_dynamic_evidence_rate)} | "
        f"{summary.p50_elapsed_ms:.0f} / {summary.p95_elapsed_ms:.0f} ms | "
        f"{summary.total_downloaded} / {summary.total_indexed} | "
        f"{summary.total_point_delta} |",
        "",
        "## 分类结果",
        "",
        "| Category | Cases | Strict Pass | Acquisition | Answer Behavior | P50 / P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {item.category} | {item.case_count} | "
        f"{item.strict_pass_rate:.2%} | {item.acquisition_rate:.2%} | "
        f"{item.answer_behavior_accuracy:.2%} | "
        f"{item.p50_elapsed_ms:.0f} / {item.p95_elapsed_ms:.0f} ms |"
        for item in report.categories
    )
    lines.extend(
        [
            "",
            "## 逐题诊断",
            "",
            "| Case | Category | Acquire | Answer | Dynamic Evidence | "
            "Target Citation | Points | Strict |",
            "| --- | --- | --- | --- | ---: | --- | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {item.case_id} | {item.category} | "
        f"{item.acquisition_rounds}:{item.acquisition_status or '-'} | "
        f"{item.answer_status} | {item.dynamic_evidence_count}/{item.evidence_count} | "
        f"{_optional_bool(item.target_citation_hit)} | "
        f"{item.points_before}->{item.points_after} | {item.strict_pass} |"
        for item in results
    )
    lines.extend(["", "## 解释边界", ""])
    lines.extend(f"- {note}" for note in report.config.notes)
    return "\n".join(lines) + "\n"


def _optional_rate(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _optional_bool(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "yes" if value else "no"
