"""Deterministic pypdf baseline metrics for visually reviewed PDF pages."""

import hashlib
import math
import re
import time
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

from paper_research_copilot.evaluation.parse_datasets import (
    ParseBenchmarkCase,
    ParseCategory,
)

SHORT_PAGE_CHAR_THRESHOLD = 200
CONTROL_RATIO_THRESHOLD = 0.002
REPLACEMENT_RATIO_THRESHOLD = 0.001

PageExtractor = Callable[[Path, int], tuple[str, float]]


class ParseCharacterMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    char_count: int = Field(ge=0)
    line_count: int = Field(ge=0)
    replacement_char_count: int = Field(ge=0)
    replacement_char_ratio: float = Field(ge=0, le=1)
    control_char_count: int = Field(ge=0)
    control_char_ratio: float = Field(ge=0, le=1)
    private_use_char_count: int = Field(ge=0)
    private_use_char_ratio: float = Field(ge=0, le=1)
    non_printable_char_count: int = Field(ge=0)
    non_printable_char_ratio: float = Field(ge=0, le=1)


class ParseTableQuestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    expected_answer: str
    answer_present: bool
    context_anchors_pass: bool


class ParseCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    paper_id: str
    page_number: int = Field(ge=1)
    category: ParseCategory
    status: Literal["ok", "empty", "short", "suspicious"]
    extract_latency_ms: float = Field(ge=0)
    metrics: ParseCharacterMetrics
    quality_flags: tuple[str, ...]
    text_layer_expectation_pass: bool
    expected_contains_pass: bool
    table_questions_pass: bool | None
    table_question_results: tuple[ParseTableQuestionResult, ...]
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview: str


class ParseCategorySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: ParseCategory
    case_count: int = Field(ge=1)
    empty_rate: float = Field(ge=0, le=1)
    short_rate: float = Field(ge=0, le=1)
    suspicious_rate: float = Field(ge=0, le=1)
    expected_anchor_pass_rate: float = Field(ge=0, le=1)
    table_question_pass_rate: float | None = Field(default=None, ge=0, le=1)


class ParseBenchmarkConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser: Literal["pypdf"] = "pypdf"
    parser_version: str
    normalization_version: Literal["pdf_text_v1"] = "pdf_text_v1"
    short_page_char_threshold: int = Field(ge=1)
    control_ratio_threshold: float = Field(ge=0, le=1)
    replacement_ratio_threshold: float = Field(ge=0, le=1)


class ParseBenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: ParseBenchmarkConfig
    case_count: int = Field(ge=1)
    empty_rate: float = Field(ge=0, le=1)
    short_page_rate: float = Field(ge=0, le=1)
    suspicious_char_case_rate: float = Field(ge=0, le=1)
    text_layer_expectation_pass_rate: float = Field(ge=0, le=1)
    expected_anchor_pass_rate: float = Field(ge=0, le=1)
    table_question_pass_rate: float | None = Field(default=None, ge=0, le=1)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    by_category: tuple[ParseCategorySummary, ...]
    results: tuple[ParseCaseResult, ...]


def extract_page_with_pypdf(path: Path, page_number: int) -> tuple[str, float]:
    """Extract one 1-based page and include document-open cost in latency."""

    started = time.perf_counter()
    reader = PdfReader(path)
    text = _normalize_text(reader.pages[page_number - 1].extract_text() or "")
    latency_ms = (time.perf_counter() - started) * 1000
    return text, latency_ms


def run_parse_benchmark(
    cases: Sequence[ParseBenchmarkCase],
    *,
    project_root: Path,
    extractor: PageExtractor = extract_page_with_pypdf,
) -> tuple[ParseCaseResult, ...]:
    results: list[ParseCaseResult] = []
    for case in cases:
        pdf_path = (project_root / case.pdf_path).resolve()
        text, latency_ms = extractor(pdf_path, case.page_number)
        metrics = calculate_character_metrics(text)
        flags = _quality_flags(metrics)
        table_results = tuple(
            ParseTableQuestionResult(
                question=item.question,
                expected_answer=item.expected_answer,
                answer_present=_contains(text, item.expected_answer),
                context_anchors_pass=all(
                    _contains(text, anchor) for anchor in item.required_context
                ),
            )
            for item in case.table_questions
        )
        if not text:
            status: Literal["ok", "empty", "short", "suspicious"] = "empty"
        elif "short_page" in flags:
            status = "short"
        elif flags:
            status = "suspicious"
        else:
            status = "ok"
        results.append(
            ParseCaseResult(
                case_id=case.case_id,
                paper_id=case.paper_id,
                page_number=case.page_number,
                category=case.category,
                status=status,
                extract_latency_ms=round(latency_ms, 2),
                metrics=metrics,
                quality_flags=flags,
                text_layer_expectation_pass=bool(text) == case.expected_text_layer,
                expected_contains_pass=all(
                    _contains(text, anchor) for anchor in case.expected_contains
                ),
                table_questions_pass=(
                    all(item.answer_present and item.context_anchors_pass for item in table_results)
                    if table_results
                    else None
                ),
                table_question_results=table_results,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                preview=_preview(text),
            )
        )
    return tuple(results)


def calculate_character_metrics(text: str) -> ParseCharacterMetrics:
    length = len(text)
    replacement_count = text.count("\ufffd")
    control_count = sum(
        unicodedata.category(character) == "Cc" and character not in "\n\t" for character in text
    )
    private_use_count = sum(unicodedata.category(character) == "Co" for character in text)
    non_printable_count = sum(
        not character.isprintable() and character not in "\n\t" for character in text
    )
    denominator = max(length, 1)
    return ParseCharacterMetrics(
        char_count=length,
        line_count=len(text.splitlines()) if text else 0,
        replacement_char_count=replacement_count,
        replacement_char_ratio=round(replacement_count / denominator, 6),
        control_char_count=control_count,
        control_char_ratio=round(control_count / denominator, 6),
        private_use_char_count=private_use_count,
        private_use_char_ratio=round(private_use_count / denominator, 6),
        non_printable_char_count=non_printable_count,
        non_printable_char_ratio=round(non_printable_count / denominator, 6),
    )


def build_parse_benchmark_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    project_root: Path,
) -> ParseBenchmarkConfig:
    resolved_dataset = dataset_path.resolve()
    try:
        display_path = resolved_dataset.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved_dataset)
    return ParseBenchmarkConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=display_path,
        dataset_sha256=hashlib.sha256(resolved_dataset.read_bytes()).hexdigest(),
        parser_version=version("pypdf"),
        short_page_char_threshold=SHORT_PAGE_CHAR_THRESHOLD,
        control_ratio_threshold=CONTROL_RATIO_THRESHOLD,
        replacement_ratio_threshold=REPLACEMENT_RATIO_THRESHOLD,
    )


def build_parse_benchmark_report(
    results: Sequence[ParseCaseResult],
    config: ParseBenchmarkConfig,
) -> ParseBenchmarkReport:
    if not results:
        raise ValueError("Cannot build a parse benchmark report without case results")
    table_results = [result for result in results if result.table_questions_pass is not None]
    latencies = [result.extract_latency_ms for result in results]
    categories = sorted({result.category for result in results})
    return ParseBenchmarkReport(
        config=config,
        case_count=len(results),
        empty_rate=_rate(result.status == "empty" for result in results),
        short_page_rate=_rate(result.status == "short" for result in results),
        suspicious_char_case_rate=_rate(result.status == "suspicious" for result in results),
        text_layer_expectation_pass_rate=_rate(
            result.text_layer_expectation_pass for result in results
        ),
        expected_anchor_pass_rate=_rate(result.expected_contains_pass for result in results),
        table_question_pass_rate=(
            _rate(bool(result.table_questions_pass) for result in table_results)
            if table_results
            else None
        ),
        p50_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_latency_ms=round(_percentile(latencies, 0.95), 2),
        by_category=tuple(
            _category_summary(
                category,
                [result for result in results if result.category == category],
            )
            for category in categories
        ),
        results=tuple(results),
    )


def write_parse_benchmark_artifacts(
    report: ParseBenchmarkReport,
    *,
    baseline_dir: Path,
) -> tuple[Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _contains(text: str, expected: str) -> bool:
    normalized_text = " ".join(text.split()).casefold()
    normalized_expected = " ".join(expected.split()).casefold()
    return normalized_expected in normalized_text


def _quality_flags(metrics: ParseCharacterMetrics) -> tuple[str, ...]:
    flags: list[str] = []
    if metrics.char_count == 0:
        flags.append("empty_page")
    elif metrics.char_count < SHORT_PAGE_CHAR_THRESHOLD:
        flags.append("short_page")
    if metrics.control_char_ratio > CONTROL_RATIO_THRESHOLD:
        flags.append("control_chars")
    if (
        metrics.replacement_char_ratio + metrics.private_use_char_ratio
        > REPLACEMENT_RATIO_THRESHOLD
    ):
        flags.append("replacement_or_private_use_chars")
    return tuple(flags)


def _preview(text: str, limit: int = 240) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _category_summary(
    category: ParseCategory,
    results: Sequence[ParseCaseResult],
) -> ParseCategorySummary:
    table_results = [result for result in results if result.table_questions_pass is not None]
    return ParseCategorySummary(
        category=category,
        case_count=len(results),
        empty_rate=_rate(result.status == "empty" for result in results),
        short_rate=_rate(result.status == "short" for result in results),
        suspicious_rate=_rate(result.status == "suspicious" for result in results),
        expected_anchor_pass_rate=_rate(result.expected_contains_pass for result in results),
        table_question_pass_rate=(
            _rate(bool(result.table_questions_pass) for result in table_results)
            if table_results
            else None
        ),
    )


def _rate(values: Iterable[bool]) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 4)


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _markdown_report(report: ParseBenchmarkReport) -> str:
    config = report.config
    table_rate = (
        f"{report.table_question_pass_rate:.2%}"
        if report.table_question_pass_rate is not None
        else "N/A"
    )
    lines = [
        f"# PDF Parse Baseline：{config.baseline_id}",
        "",
        f"- 评估日期：`{config.evaluated_on}`",
        f"- Dataset：`{config.dataset_path}`（{report.case_count} cases）",
        f"- Parser：`{config.parser}=={config.parser_version}`",
        f"- Normalization：`{config.normalization_version}`",
        "- 运行边界：只读取本地 PDF，不调用 Embedding、LLM 或 Qdrant。",
        "",
        "## 总体指标",
        "",
        "| Empty | Short | Suspicious chars | Text-layer expectation | "
        "Text anchors | Table anchors | P50 / P95 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.empty_rate:.2%} | {report.short_page_rate:.2%} | "
        f"{report.suspicious_char_case_rate:.2%} | "
        f"{report.text_layer_expectation_pass_rate:.2%} | "
        f"{report.expected_anchor_pass_rate:.2%} | {table_rate} | "
        f"{report.p50_latency_ms:.2f} / {report.p95_latency_ms:.2f} ms |",
        "",
        "Table anchors 只验证答案字符串和行列上下文仍在抽取文本中，不代表 Parser 已恢复表格结构。",
        "",
        "## 逐页结果",
        "",
        "| Case | Category | Page | Status | Chars | Control | Private use | "
        "Anchors | Table | Latency |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for result in report.results:
        table_pass = (
            str(result.table_questions_pass) if result.table_questions_pass is not None else "-"
        )
        lines.append(
            f"| {result.case_id} | {result.category} | {result.page_number} | "
            f"{result.status} | {result.metrics.char_count} | "
            f"{result.metrics.control_char_ratio:.4%} | "
            f"{result.metrics.private_use_char_ratio:.4%} | "
            f"{result.expected_contains_pass} | {table_pass} | "
            f"{result.extract_latency_ms:.2f} ms |"
        )
    lines.extend(
        [
            "",
            "## Baseline 解释",
            "",
            "- `empty` 和 `short` 直接暴露纯图片页或只抽取到 Caption 的页面。",
            "- `suspicious` 使用确定性的控制字符、替代字符和 Private Use 字符比例；"
            "它不能识别所有语义乱码。",
            "- 表格、公式和双栏即使 Anchor 通过，也可能丢失二维布局或 reading order，"
            "需在后续 Parser 对照中验证。",
            "- 该报告冻结 v1 现状，Phase 1 的 Quality Router 不会回写或美化本结果。",
            "",
        ]
    )
    return "\n".join(lines)
