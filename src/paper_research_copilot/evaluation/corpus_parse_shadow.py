"""Corpus-wide shadow parse summaries without indexing side effects."""

import math
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import CorpusCatalog
from paper_research_copilot.ingestion import FastParserRouter


class CorpusShadowPaperResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    slug: str
    status: Literal["succeeded", "failed"]
    expected_page_count: int = Field(ge=1)
    parsed_page_count: int = Field(ge=0)
    primary_flagged_pages: int = Field(ge=0)
    accepted_pages: int = Field(ge=0)
    warning_pages: int = Field(ge=0)
    quarantined_pages: int = Field(ge=0)
    secondary_selected_pages: int = Field(ge=0)
    recovered_pages: int = Field(ge=0)
    primary_flagged_page_numbers: tuple[int, ...] = ()
    secondary_selected_page_numbers: tuple[int, ...] = ()
    warning_page_numbers: tuple[int, ...] = ()
    structured_fallback_pages: tuple[int, ...] = ()
    total_latency_ms: float = Field(ge=0)
    error: str | None = None


class CorpusShadowConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_id: str
    evaluated_on: str
    corpus_id: str
    corpus_version: int = Field(ge=1)
    primary_parser: str
    secondary_parser: str
    shadow_mode: bool = True


class CorpusShadowReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: CorpusShadowConfig
    paper_count: int = Field(ge=1)
    successful_papers: int = Field(ge=0)
    failed_papers: int = Field(ge=0)
    open_rate: float = Field(ge=0, le=1)
    page_count: int = Field(ge=0)
    primary_flagged_pages: int = Field(ge=0)
    secondary_selected_pages: int = Field(ge=0)
    recovered_pages: int = Field(ge=0)
    selected_warning_pages: int = Field(ge=0)
    selected_quarantined_pages: int = Field(ge=0)
    selected_quarantine_page_rate: float = Field(ge=0, le=1)
    p50_document_latency_ms: float = Field(ge=0)
    p95_document_latency_ms: float = Field(ge=0)
    papers_requiring_structured_fallback: tuple[str, ...]
    results: tuple[CorpusShadowPaperResult, ...]


def run_corpus_parse_shadow(
    catalog: CorpusCatalog,
    *,
    router: FastParserRouter,
    progress: Callable[[CorpusShadowPaperResult, int, int], None] | None = None,
) -> tuple[CorpusShadowPaperResult, ...]:
    results: list[CorpusShadowPaperResult] = []
    total = len(catalog.papers)
    for index, asset in enumerate(catalog.papers, start=1):
        try:
            document = router.parse(asset.pdf_path, shadow_mode=True)
            if document.document_sha256 != asset.manifest.sha256:
                raise ValueError("Shadow parse PDF SHA-256 differs from Corpus manifest")
            primary_candidates = [page.candidates[0] for page in document.pages]
            result = CorpusShadowPaperResult(
                paper_id=asset.spec.paper_id,
                slug=asset.spec.slug,
                status="succeeded",
                expected_page_count=asset.manifest.page_count,
                parsed_page_count=document.page_count,
                primary_flagged_pages=sum(
                    item.quality.status != "accepted" for item in primary_candidates
                ),
                accepted_pages=document.accepted_pages,
                warning_pages=document.warning_pages,
                quarantined_pages=document.quarantined_pages,
                secondary_selected_pages=document.secondary_selected_pages,
                recovered_pages=sum(
                    primary.quality.status != "accepted" and page.quality_status == "accepted"
                    for primary, page in zip(primary_candidates, document.pages, strict=True)
                ),
                primary_flagged_page_numbers=tuple(
                    primary.extraction.page_number
                    for primary in primary_candidates
                    if primary.quality.status != "accepted"
                ),
                secondary_selected_page_numbers=tuple(
                    page.page_number
                    for page in document.pages
                    if page.parser_name == router.secondary.parser_name
                ),
                warning_page_numbers=tuple(
                    page.page_number for page in document.pages if page.quality_status == "warning"
                ),
                structured_fallback_pages=tuple(
                    page.page_number
                    for page in document.pages
                    if page.route_action == "structured_fallback_required"
                ),
                total_latency_ms=document.total_latency_ms,
            )
        except Exception as exc:
            result = CorpusShadowPaperResult(
                paper_id=asset.spec.paper_id,
                slug=asset.spec.slug,
                status="failed",
                expected_page_count=asset.manifest.page_count,
                parsed_page_count=0,
                primary_flagged_pages=0,
                accepted_pages=0,
                warning_pages=0,
                quarantined_pages=0,
                secondary_selected_pages=0,
                recovered_pages=0,
                total_latency_ms=0,
                error=f"{type(exc).__name__}: {exc}",
            )
        results.append(result)
        if progress is not None:
            progress(result, index, total)
    return tuple(results)


def build_corpus_shadow_config(
    *,
    report_id: str,
    catalog: CorpusCatalog,
    router: FastParserRouter,
) -> CorpusShadowConfig:
    return CorpusShadowConfig(
        report_id=report_id,
        evaluated_on=date.today().isoformat(),
        corpus_id=catalog.spec.corpus_id,
        corpus_version=catalog.spec.version,
        primary_parser=f"{router.primary.parser_name}=={router.primary.parser_version}",
        secondary_parser=f"{router.secondary.parser_name}=={router.secondary.parser_version}",
    )


def build_corpus_shadow_report(
    results: Sequence[CorpusShadowPaperResult],
    config: CorpusShadowConfig,
) -> CorpusShadowReport:
    if not results:
        raise ValueError("Cannot build a Corpus shadow report without paper results")
    successful = [result for result in results if result.status == "succeeded"]
    page_count = sum(result.parsed_page_count for result in successful)
    latencies = [result.total_latency_ms for result in successful]
    quarantined_pages = sum(result.quarantined_pages for result in successful)
    return CorpusShadowReport(
        config=config,
        paper_count=len(results),
        successful_papers=len(successful),
        failed_papers=len(results) - len(successful),
        open_rate=round(len(successful) / len(results), 4),
        page_count=page_count,
        primary_flagged_pages=sum(result.primary_flagged_pages for result in successful),
        secondary_selected_pages=sum(result.secondary_selected_pages for result in successful),
        recovered_pages=sum(result.recovered_pages for result in successful),
        selected_warning_pages=sum(result.warning_pages for result in successful),
        selected_quarantined_pages=quarantined_pages,
        selected_quarantine_page_rate=(
            round(quarantined_pages / page_count, 6) if page_count else 0
        ),
        p50_document_latency_ms=(round(_percentile(latencies, 0.50), 2) if latencies else 0),
        p95_document_latency_ms=(round(_percentile(latencies, 0.95), 2) if latencies else 0),
        papers_requiring_structured_fallback=tuple(
            result.paper_id for result in successful if result.structured_fallback_pages
        ),
        results=tuple(results),
    )


def write_corpus_shadow_artifacts(
    report: CorpusShadowReport,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{report.config.report_id}.json"
    markdown_path = output_dir / f"{report.config.report_id}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _markdown_report(report: CorpusShadowReport) -> str:
    config = report.config
    lines = [
        f"# Corpus Parse Shadow：{config.report_id}",
        "",
        f"- Corpus：`{config.corpus_id}` / v{config.corpus_version}",
        f"- Primary：`{config.primary_parser}`",
        f"- Secondary：`{config.secondary_parser}`",
        "- Mode：Shadow；不执行 Chunk、Embedding 或 Qdrant 写入。",
        "",
        "## 汇总",
        "",
        "| Papers | Open rate | Pages | Primary flagged | Secondary selected | Recovered | "
        "Warning | Quarantined | Quarantine rate | P50 / P95 document |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {report.paper_count} | {report.open_rate:.2%} | {report.page_count} | "
        f"{report.primary_flagged_pages} | {report.secondary_selected_pages} | "
        f"{report.recovered_pages} | {report.selected_warning_pages} | "
        f"{report.selected_quarantined_pages} | "
        f"{report.selected_quarantine_page_rate:.4%} | "
        f"{report.p50_document_latency_ms:.2f} / {report.p95_document_latency_ms:.2f} ms |",
        "",
        "## 逐篇结果",
        "",
        "| Paper | Status | Pages | Primary flagged | Secondary pages | Recovered | "
        "Warning pages | Structured fallback pages | Latency |",
        "| --- | --- | ---: | ---: | --- | ---: | --- | --- | ---: |",
    ]
    for result in report.results:
        secondary = ", ".join(f"p{page}" for page in result.secondary_selected_page_numbers) or "-"
        warning = ", ".join(f"p{page}" for page in result.warning_page_numbers) or "-"
        fallback = ", ".join(f"p{page}" for page in result.structured_fallback_pages) or "-"
        lines.append(
            f"| {result.paper_id} | {result.status} | {result.parsed_page_count} | "
            f"{result.primary_flagged_pages} | {secondary} | {result.recovered_pages} | "
            f"{warning} | {fallback} | {result.total_latency_ms:.2f} ms |"
        )
        if result.error:
            lines.append(f"| {result.paper_id} error | `{result.error}` | | | | | | | |")
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "- Primary flagged 表示需要对照，不等同于页面不可用。",
            "- Quarantined 页面必须经过 Structured Parser 或人工处理后才能进入未来索引。",
            "- 本报告不改变 Corpus v3 Manifest、Chunk 或现有 Qdrant Collection。",
            "",
        ]
    )
    return "\n".join(lines)
