"""Deterministic evaluation for page-aware structured parser outputs."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain.structured_parse import (
    StructuredBlockType,
    StructuredPageResult,
)
from paper_research_copilot.evaluation.structured_parse_datasets import (
    StructuredParseBenchmarkCase,
    StructuredParseCategory,
    StructuredTableQuestion,
)


class StructuredTableQuestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: str
    row_label: str
    column_headers: tuple[str, ...]
    expected_answer: str
    actual_answer: str | None
    relationship_pass: bool
    table_block_id: str | None


class StructuredParseCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    source_id: str
    page_number: int = Field(ge=1)
    category: StructuredParseCategory
    method: Literal["auto", "txt", "ocr"]
    status: Literal["pass", "fail", "error"]
    error: str | None = None
    latency_ms: float = Field(ge=0)
    block_count: int = Field(ge=0)
    matched_anchors: tuple[str, ...]
    missing_anchors: tuple[str, ...]
    anchor_recall: float = Field(ge=0, le=1)
    required_block_types_pass: bool
    missing_required_block_types: tuple[StructuredBlockType, ...]
    bbox_provenance_completeness: float = Field(ge=0, le=1)
    page_provenance_completeness: float = Field(ge=0, le=1)
    table_questions_pass: bool | None
    table_question_results: tuple[StructuredTableQuestionResult, ...]


class StructuredParseConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_id: str
    evaluated_on: str
    dataset_path: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser: Literal["mineru"] = "mineru"
    parser_version: str
    backend: str
    device: str
    worker_mode: str
    formula_policy: str


class StructuredParseReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: StructuredParseConfig
    case_count: int = Field(ge=1)
    case_success_rate: float = Field(ge=0, le=1)
    text_anchor_recall: float = Field(ge=0, le=1)
    required_block_type_pass_rate: float = Field(ge=0, le=1)
    bbox_provenance_completeness: float = Field(ge=0, le=1)
    page_provenance_completeness: float = Field(ge=0, le=1)
    table_qa_accuracy: float | None = Field(default=None, ge=0, le=1)
    ocr_recovery_rate: float | None = Field(default=None, ge=0, le=1)
    cold_start_latency_ms: float = Field(ge=0)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    results: tuple[StructuredParseCaseResult, ...]


def evaluate_structured_parse_case(
    case: StructuredParseBenchmarkCase,
    parsed: StructuredPageResult,
) -> StructuredParseCaseResult:
    if parsed.page_number != case.page_number:
        raise ValueError(
            f"Parsed page {parsed.page_number} does not match "
            f"{case.case_id} page {case.page_number}"
        )
    searchable = "\n".join(
        [parsed.markdown, *(block.text for block in parsed.blocks if block.text)]
    )
    matched = tuple(anchor for anchor in case.expected_contains if _contains(searchable, anchor))
    missing = tuple(anchor for anchor in case.expected_contains if anchor not in matched)
    observed_types = {block.block_type for block in parsed.blocks}
    missing_types = tuple(
        block_type
        for block_type in case.required_block_types
        if block_type not in observed_types
    )
    block_count = len(parsed.blocks)
    bbox_completeness = _fraction(
        sum(block.bbox is not None for block in parsed.blocks), block_count
    )
    page_completeness = _fraction(
        sum(block.page_number == case.page_number for block in parsed.blocks), block_count
    )
    table_results = tuple(
        evaluate_table_question(question, parsed) for question in case.table_questions
    )
    table_pass = (
        all(result.relationship_pass for result in table_results) if table_results else None
    )
    anchor_recall = _fraction(len(matched), len(case.expected_contains))
    passed = (
        not missing
        and not missing_types
        and bbox_completeness == 1
        and page_completeness == 1
        and table_pass is not False
    )
    return StructuredParseCaseResult(
        case_id=case.case_id,
        source_id=case.source_id,
        page_number=case.page_number,
        category=case.category,
        method=case.method,
        status="pass" if passed else "fail",
        latency_ms=parsed.latency_ms,
        block_count=block_count,
        matched_anchors=matched,
        missing_anchors=missing,
        anchor_recall=anchor_recall,
        required_block_types_pass=not missing_types,
        missing_required_block_types=missing_types,
        bbox_provenance_completeness=bbox_completeness,
        page_provenance_completeness=page_completeness,
        table_questions_pass=table_pass,
        table_question_results=table_results,
    )


def build_structured_parse_error_result(
    case: StructuredParseBenchmarkCase,
    *,
    error: str,
    latency_ms: float,
) -> StructuredParseCaseResult:
    return StructuredParseCaseResult(
        case_id=case.case_id,
        source_id=case.source_id,
        page_number=case.page_number,
        category=case.category,
        method=case.method,
        status="error",
        error=error,
        latency_ms=latency_ms,
        block_count=0,
        matched_anchors=(),
        missing_anchors=case.expected_contains,
        anchor_recall=0,
        required_block_types_pass=False,
        missing_required_block_types=case.required_block_types,
        bbox_provenance_completeness=0,
        page_provenance_completeness=0,
        table_questions_pass=False if case.table_questions else None,
        table_question_results=(),
    )


def evaluate_table_question(
    question: StructuredTableQuestion,
    parsed: StructuredPageResult,
) -> StructuredTableQuestionResult:
    best_actual: str | None = None
    best_block_id: str | None = None
    for block in parsed.blocks:
        if block.block_type != "table" or not block.html:
            continue
        actual = _lookup_table_cell(
            block.html,
            row_label=question.row_label,
            column_headers=question.column_headers,
        )
        if actual is None:
            continue
        best_actual = actual
        best_block_id = block.block_id
        if _equivalent(actual, question.expected_answer):
            return StructuredTableQuestionResult(
                **question.model_dump(),
                actual_answer=actual,
                relationship_pass=True,
                table_block_id=block.block_id,
            )
    return StructuredTableQuestionResult(
        **question.model_dump(),
        actual_answer=best_actual,
        relationship_pass=False,
        table_block_id=best_block_id,
    )


def build_structured_parse_config(
    *,
    baseline_id: str,
    dataset_path: Path,
    project_root: Path,
    parser_version: str,
    backend: str,
    device: str,
    worker_mode: str,
    formula_policy: str,
) -> StructuredParseConfig:
    resolved_dataset = dataset_path.resolve()
    try:
        display_path = resolved_dataset.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display_path = str(resolved_dataset)
    return StructuredParseConfig(
        baseline_id=baseline_id,
        evaluated_on=date.today().isoformat(),
        dataset_path=display_path,
        dataset_sha256=hashlib.sha256(resolved_dataset.read_bytes()).hexdigest(),
        parser_version=parser_version,
        backend=backend,
        device=device,
        worker_mode=worker_mode,
        formula_policy=formula_policy,
    )


def build_structured_parse_report(
    results: Sequence[StructuredParseCaseResult],
    config: StructuredParseConfig,
) -> StructuredParseReport:
    if not results:
        raise ValueError("Cannot build a structured parse report without results")
    table_results = [
        item for result in results for item in result.table_question_results
    ]
    ocr_results = [result for result in results if result.method == "ocr"]
    anchor_total = sum(
        len(result.matched_anchors) + len(result.missing_anchors) for result in results
    )
    anchor_matches = sum(len(result.matched_anchors) for result in results)
    block_total = sum(result.block_count for result in results)
    latencies = [result.latency_ms for result in results]
    return StructuredParseReport(
        config=config,
        case_count=len(results),
        case_success_rate=_rate(result.status == "pass" for result in results),
        text_anchor_recall=_fraction(anchor_matches, anchor_total),
        required_block_type_pass_rate=_rate(
            result.required_block_types_pass for result in results
        ),
        bbox_provenance_completeness=_weighted_completeness(
            results, "bbox_provenance_completeness", block_total
        ),
        page_provenance_completeness=_weighted_completeness(
            results, "page_provenance_completeness", block_total
        ),
        table_qa_accuracy=(
            _rate(item.relationship_pass for item in table_results)
            if table_results
            else None
        ),
        ocr_recovery_rate=(
            _rate(result.anchor_recall == 1 for result in ocr_results)
            if ocr_results
            else None
        ),
        cold_start_latency_ms=latencies[0],
        p50_latency_ms=round(_percentile(latencies, 0.50), 2),
        p95_latency_ms=round(_percentile(latencies, 0.95), 2),
        results=tuple(results),
    )


def write_structured_parse_artifacts(
    report: StructuredParseReport,
    *,
    baseline_dir: Path,
) -> tuple[Path, Path]:
    baseline_dir.mkdir(parents=True, exist_ok=True)
    json_path = baseline_dir / f"{report.config.baseline_id}.json"
    markdown_path = baseline_dir / f"{report.config.baseline_id}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


@dataclass(frozen=True)
class _Cell:
    text: str
    rowspan: int
    colspan: int


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[_Cell]] = []
        self._row: list[_Cell] | None = None
        self._parts: list[str] | None = None
        self._rowspan = 1
        self._colspan = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            values = dict(attrs)
            self._parts = []
            self._rowspan = _positive_int(values.get("rowspan"))
            self._colspan = _positive_int(values.get("colspan"))

    def handle_data(self, data: str) -> None:
        if self._parts is not None and data.strip():
            self._parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._parts is not None:
            self._row.append(
                _Cell(" ".join(self._parts), self._rowspan, self._colspan)
            )
            self._parts = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _lookup_table_cell(
    html: str,
    *,
    row_label: str,
    column_headers: Sequence[str],
) -> str | None:
    parser = _TableParser()
    parser.feed(html)
    parser.close()
    grid = _expand_grid(parser.rows)
    target_row = next(
        (
            row_index
            for row_index, row in enumerate(grid)
            if any(_equivalent(value, row_label) for value in row)
        ),
        None,
    )
    if target_row is None:
        return None
    row = grid[target_row]
    for column_index, actual in enumerate(row):
        if _equivalent(actual, row_label):
            continue
        header_path = [grid[index][column_index] for index in range(target_row)]
        if all(
            any(_contains(value, header) for value in header_path)
            for header in column_headers
        ):
            return actual
    return None


def _expand_grid(rows: Sequence[Sequence[_Cell]]) -> list[list[str]]:
    occupied: dict[tuple[int, int], str] = {}
    max_column = 0
    for row_index, cells in enumerate(rows):
        column_index = 0
        for cell in cells:
            while (row_index, column_index) in occupied:
                column_index += 1
            for row_offset in range(cell.rowspan):
                for column_offset in range(cell.colspan):
                    occupied[(row_index + row_offset, column_index + column_offset)] = cell.text
            column_index += cell.colspan
            max_column = max(max_column, column_index)
    return [
        [occupied.get((row_index, column_index), "") for column_index in range(max_column)]
        for row_index in range(len(rows))
    ]


def _positive_int(value: str | None) -> int:
    try:
        return max(1, int(value or "1"))
    except ValueError:
        return 1


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def _contains(value: str, expected: str) -> bool:
    return _normalize(expected) in _normalize(value)


def _equivalent(value: str, expected: str) -> bool:
    return _normalize(value).strip("%") == _normalize(expected).strip("%")


def _fraction(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _rate(values: Iterable[bool]) -> float:
    materialized = list(values)
    return _fraction(sum(materialized), len(materialized))


def _weighted_completeness(
    results: Sequence[StructuredParseCaseResult],
    field: Literal["bbox_provenance_completeness", "page_provenance_completeness"],
    block_total: int,
) -> float:
    completed = sum(getattr(result, field) * result.block_count for result in results)
    return round(completed / block_total, 4) if block_total else 0.0


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _markdown_report(report: StructuredParseReport) -> str:
    config = report.config
    table_accuracy = (
        f"{report.table_qa_accuracy:.2%}" if report.table_qa_accuracy is not None else "N/A"
    )
    ocr_rate = (
        f"{report.ocr_recovery_rate:.2%}" if report.ocr_recovery_rate is not None else "N/A"
    )
    lines = [
        f"# Structured Parse Benchmark：{config.baseline_id}",
        "",
        f"- 评估日期：`{config.evaluated_on}`",
        f"- Dataset：`{config.dataset_path}`（{report.case_count} cases）",
        f"- Parser：`MinerU {config.parser_version}` / `{config.backend}` / `{config.device}`",
        f"- Worker：`{config.worker_mode}`",
        f"- Formula policy：`{config.formula_policy}`",
        "- 边界：只解析隔离的单页 Case，不修改 Corpus、Chunk、Embedding 或 Qdrant。",
        "",
        "## 总体指标",
        "",
        "| Case pass | Text anchor recall | Block type | BBox provenance | "
        "Page provenance | Table QA | OCR recovery | P50 / P95 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.case_success_rate:.2%} | {report.text_anchor_recall:.2%} | "
        f"{report.required_block_type_pass_rate:.2%} | "
        f"{report.bbox_provenance_completeness:.2%} | "
        f"{report.page_provenance_completeness:.2%} | {table_accuracy} | {ocr_rate} | "
        f"{report.p50_latency_ms:.2f} / {report.p95_latency_ms:.2f} ms |",
        "",
        "Table QA 按行标签与一层或多层列头定位交叉单元格；答案出现在错误列不会得分。",
        "",
        "## 逐 Case 结果",
        "",
        "| Case | Category | Method | Status | Anchors | Blocks | BBox | Table | Latency |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for result in report.results:
        table_pass = (
            str(result.table_questions_pass) if result.table_questions_pass is not None else "-"
        )
        lines.append(
            f"| {result.case_id} | {result.category} | {result.method} | {result.status} | "
            f"{result.anchor_recall:.2%} | {result.block_count} | "
            f"{result.bbox_provenance_completeness:.2%} | {table_pass} | "
            f"{result.latency_ms:.2f} ms |"
        )
        if result.error:
            lines.append(f"\n`{result.case_id}` error：{result.error}\n")
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- 当前 Runner 每个 Case 启动一个隔离进程，因此延迟包含 Python、PyTorch 与模型冷启动。",
            "- `OCR recovery` 代表强制 OCR Case 的全部人工 Anchor 被恢复，不代表全文字符完全正确。",
            "- `Table QA` 验证结构关系；它比只判断答案字符串是否出现更严格。",
            "- Formula Case 单独启用公式模型，其余 Case 关闭公式模型以降低无关资源消耗。",
            "",
        ]
    )
    return "\n".join(lines)
