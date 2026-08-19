"""Shadow evaluation for the fast PDF parser router."""

import hashlib
import math
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import (
    DocumentParseResult,
    PageParseCandidate,
    ParseQualityStatus,
    ParserName,
    ParseRouteAction,
)
from paper_research_copilot.evaluation.parse_datasets import (
    ParseBenchmarkCase,
    ParseCategory,
)
from paper_research_copilot.ingestion import FastParserRouter

KNOWN_ISSUE_CATEGORIES: frozenset[ParseCategory] = frozenset(
    {
        "garbled_text",
        "mixed_text_and_garbled_figure",
        "short_visual_page",
        "image_only",
    }
)


class ShadowParserSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    parser_name: ParserName
    parser_version: str
    status: ParseQualityStatus
    score: float = Field(ge=0, le=1)
    char_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    text_anchor_pass: bool
    table_anchor_pass: bool | None
    signals: tuple[str, ...]


class ShadowParseCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    category: ParseCategory
    paper_id: str
    page_number: int = Field(ge=1)
    primary: ShadowParserSnapshot
    secondary: ShadowParserSnapshot
    selected_parser: ParserName
    selected_status: ParseQualityStatus
    selected_score: float = Field(ge=0, le=1)
    route_action: ParseRouteAction
    selection_reason: str
    selected_text_anchor_pass: bool
    selected_table_anchor_pass: bool | None


class ShadowParseConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    router_version: str = "fast_parser_router_v1"
    primary_parser: str
    secondary_parser: str
    shadow_mode: bool = True


class ShadowParseReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: ShadowParseConfig
    case_count: int = Field(ge=1)
    known_issue_count: int = Field(ge=1)
    primary_issue_detection_rate: float = Field(ge=0, le=1)
    known_issue_recovery_rate: float | None = Field(default=None, ge=0, le=1)
    clean_primary_retention_rate: float = Field(ge=0, le=1)
    secondary_selection_rate: float = Field(ge=0, le=1)
    selected_accepted_rate: float = Field(ge=0, le=1)
    selected_warning_rate: float = Field(ge=0, le=1)
    structured_fallback_rate: float = Field(ge=0, le=1)
    selected_text_anchor_pass_rate: float = Field(ge=0, le=1)
    selected_table_anchor_pass_rate: float | None = Field(default=None, ge=0, le=1)
    p50_case_latency_ms: float = Field(ge=0)
    p95_case_latency_ms: float = Field(ge=0)
    results: tuple[ShadowParseCaseResult, ...]


def run_shadow_parse_benchmark(
    cases: Sequence[ParseBenchmarkCase],
    *,
    project_root: Path,
    router: FastParserRouter,
) -> tuple[ShadowParseCaseResult, ...]:
    documents: dict[Path, DocumentParseResult] = {}
    results: list[ShadowParseCaseResult] = []
    for case in cases:
        pdf_path = (project_root / case.pdf_path).resolve()
        document = documents.get(pdf_path)
        if document is None:
            document = router.parse(pdf_path, shadow_mode=True)
            documents[pdf_path] = document
        page = document.pages[case.page_number - 1]
        candidates = {candidate.extraction.parser_name: candidate for candidate in page.candidates}
        primary = candidates[router.primary.parser_name]
        secondary = candidates[router.secondary.parser_name]
        results.append(
            ShadowParseCaseResult(
                case_id=case.case_id,
                category=case.category,
                paper_id=case.paper_id,
                page_number=case.page_number,
                primary=_snapshot(primary, case),
                secondary=_snapshot(secondary, case),
                selected_parser=page.parser_name,
                selected_status=page.quality_status,
                selected_score=page.quality_score,
                route_action=page.route_action,
                selection_reason=page.selection_reason,
                selected_text_anchor_pass=_text_anchor_pass(page.text, case),
                selected_table_anchor_pass=_table_anchor_pass(page.text, case),
            )
        )
    return tuple(results)


def build_shadow_parse_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    project_root: Path,
    router: FastParserRouter,
) -> ShadowParseConfig:
    resolved = dataset_path.resolve()
    try:
        display_path = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved)
    return ShadowParseConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=display_path,
        dataset_sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
        primary_parser=f"{router.primary.parser_name}=={router.primary.parser_version}",
        secondary_parser=f"{router.secondary.parser_name}=={router.secondary.parser_version}",
    )


def build_shadow_parse_report(
    results: Sequence[ShadowParseCaseResult],
    config: ShadowParseConfig,
) -> ShadowParseReport:
    if not results:
        raise ValueError("Cannot build a shadow parse report without case results")
    issue_results = [result for result in results if result.category in KNOWN_ISSUE_CATEGORIES]
    clean_results = [result for result in results if result.category not in KNOWN_ISSUE_CATEGORIES]
    recoverable = [
        result
        for result in issue_results
        if result.primary.status != "accepted" and result.secondary.status == "accepted"
    ]
    table_results = [result for result in results if result.selected_table_anchor_pass is not None]
    latencies = [result.primary.latency_ms + result.secondary.latency_ms for result in results]
    return ShadowParseReport(
        config=config,
        case_count=len(results),
        known_issue_count=len(issue_results),
        primary_issue_detection_rate=_rate(
            result.primary.status != "accepted" for result in issue_results
        ),
        known_issue_recovery_rate=(
            _rate(result.selected_status == "accepted" for result in recoverable)
            if recoverable
            else None
        ),
        clean_primary_retention_rate=_rate(
            result.route_action == "primary_accepted" for result in clean_results
        ),
        secondary_selection_rate=_rate(result.selected_parser == "pymupdf" for result in results),
        selected_accepted_rate=_rate(result.selected_status == "accepted" for result in results),
        selected_warning_rate=_rate(result.selected_status == "warning" for result in results),
        structured_fallback_rate=_rate(
            result.route_action == "structured_fallback_required" for result in results
        ),
        selected_text_anchor_pass_rate=_rate(
            result.selected_text_anchor_pass for result in results
        ),
        selected_table_anchor_pass_rate=(
            _rate(bool(result.selected_table_anchor_pass) for result in table_results)
            if table_results
            else None
        ),
        p50_case_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_case_latency_ms=round(_percentile(latencies, 0.95), 2),
        results=tuple(results),
    )


def write_shadow_parse_artifacts(
    report: ShadowParseReport,
    *,
    baseline_dir: Path,
) -> tuple[Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _snapshot(
    candidate: PageParseCandidate,
    case: ParseBenchmarkCase,
) -> ShadowParserSnapshot:
    extraction = candidate.extraction
    return ShadowParserSnapshot(
        parser_name=extraction.parser_name,
        parser_version=extraction.parser_version,
        status=candidate.quality.status,
        score=candidate.quality.score,
        char_count=candidate.quality.features.char_count,
        latency_ms=extraction.latency_ms,
        text_anchor_pass=_text_anchor_pass(extraction.text, case),
        table_anchor_pass=_table_anchor_pass(extraction.text, case),
        signals=candidate.quality.signals,
    )


def _text_anchor_pass(text: str, case: ParseBenchmarkCase) -> bool:
    return all(_contains(text, anchor) for anchor in case.expected_contains)


def _table_anchor_pass(text: str, case: ParseBenchmarkCase) -> bool | None:
    if not case.table_questions:
        return None
    return all(
        _contains(text, item.expected_answer)
        and all(_contains(text, anchor) for anchor in item.required_context)
        for item in case.table_questions
    )


def _contains(text: str, expected: str) -> bool:
    return " ".join(expected.split()).casefold() in " ".join(text.split()).casefold()


def _rate(values: Iterable[bool]) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 4)


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _markdown_report(report: ShadowParseReport) -> str:
    recovery = (
        f"{report.known_issue_recovery_rate:.2%}"
        if report.known_issue_recovery_rate is not None
        else "N/A"
    )
    table_rate = (
        f"{report.selected_table_anchor_pass_rate:.2%}"
        if report.selected_table_anchor_pass_rate is not None
        else "N/A"
    )
    lines = [
        f"# Fast Parser Shadow Baseline：{report.config.baseline_id}",
        "",
        f"- Dataset：`{report.config.dataset_path}`（{report.case_count} cases）",
        f"- Primary：`{report.config.primary_parser}`",
        f"- Secondary：`{report.config.secondary_parser}`",
        "- Mode：Shadow，只生成对照结果，不进入 Chunking、Embedding 或 Qdrant。",
        "",
        "## 总体指标",
        "",
        "| Issue detection | Recoverable issue recovery | Clean primary retention | "
        "Secondary selected | Accepted | Structured fallback | Text anchors | Table anchors |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.primary_issue_detection_rate:.2%} | {recovery} | "
        f"{report.clean_primary_retention_rate:.2%} | "
        f"{report.secondary_selection_rate:.2%} | {report.selected_accepted_rate:.2%} | "
        f"{report.structured_fallback_rate:.2%} | "
        f"{report.selected_text_anchor_pass_rate:.2%} | {table_rate} |",
        "",
        f"- Per-page extraction P50/P95：{report.p50_case_latency_ms:.2f} / "
        f"{report.p95_case_latency_ms:.2f} ms",
        "",
        "## 逐页路由",
        "",
        "| Case | Category | pypdf | PyMuPDF | Selected | Route | Text | Table |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in report.results:
        table_pass = (
            str(result.selected_table_anchor_pass)
            if result.selected_table_anchor_pass is not None
            else "-"
        )
        lines.append(
            f"| {result.case_id} | {result.category} | "
            f"{result.primary.status}/{result.primary.score:.2f} | "
            f"{result.secondary.status}/{result.secondary.score:.2f} | "
            f"{result.selected_parser}/{result.selected_status} | {result.route_action} | "
            f"{result.selected_text_anchor_pass} | {table_pass} |"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- Secondary selection 表示文本质量信号改善，不表示二维表格结构已经恢复。",
            "- Structured fallback 页面不会被允许进入索引；MinerU 尚未接入本报告。",
            "- Shadow 结果只用于校准 Router，生产 `PdfParser` 和 Corpus v3 Collection 保持不变。",
            "",
        ]
    )
    return "\n".join(lines)
