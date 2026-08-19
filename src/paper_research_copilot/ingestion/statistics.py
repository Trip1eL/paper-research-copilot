"""Chunk distribution statistics for a prepared, versioned corpus."""

import math
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from paper_research_copilot.domain import PaperChunk
from paper_research_copilot.ingestion.corpus import PreparedCorpus


class PaperChunkStatistics(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    slug: str
    page_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    mean_chars: float = Field(gt=0)
    min_chars: int = Field(gt=0)
    max_chars: int = Field(gt=0)
    section_coverage_ratio: float = Field(ge=0, le=1)


class CorpusChunkStatistics(BaseModel):
    model_config = ConfigDict(frozen=True)

    corpus_id: str
    corpus_version: int = Field(ge=1)
    generated_on: str
    chunking_version: str
    chunk_size_chars: int = Field(gt=0)
    overlap_chars: int = Field(ge=0)
    document_count: int = Field(ge=1)
    page_count: int = Field(ge=1)
    chunk_count: int = Field(ge=1)
    total_chars: int = Field(ge=1)
    mean_chars: float = Field(gt=0)
    min_chars: int = Field(gt=0)
    p50_chars: int = Field(gt=0)
    p95_chars: int = Field(gt=0)
    max_chars: int = Field(gt=0)
    short_chunk_threshold: int = Field(gt=0)
    short_chunk_count: int = Field(ge=0)
    oversized_chunk_count: int = Field(ge=0)
    duplicate_chunk_id_count: int = Field(ge=0)
    missing_required_metadata_count: int = Field(ge=0)
    section_coverage_ratio: float = Field(ge=0, le=1)
    papers: tuple[PaperChunkStatistics, ...]


def calculate_chunk_statistics(
    prepared: PreparedCorpus,
    *,
    chunking_version: str,
    chunk_size_chars: int,
    overlap_chars: int,
    short_chunk_threshold: int = 500,
) -> CorpusChunkStatistics:
    chunks = prepared.chunks
    lengths = [len(chunk.text) for chunk in chunks]
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    missing_required = sum(
        not all(
            (
                chunk.corpus_id,
                chunk.corpus_version,
                chunk.paper_id,
                chunk.arxiv_id,
                chunk.arxiv_version,
                chunk.title,
                chunk.source_path,
                chunk.page_number,
                chunk.document_sha256,
                chunk.chunking_version,
            )
        )
        for chunk in chunks
    )

    paper_stats = tuple(
        _paper_statistics(paper.asset.spec.paper_id, paper.asset.spec.slug, paper.chunks)
        for paper in prepared.papers
    )
    return CorpusChunkStatistics(
        corpus_id=prepared.catalog.spec.corpus_id,
        corpus_version=prepared.catalog.spec.version,
        generated_on=date.today().isoformat(),
        chunking_version=chunking_version,
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
        document_count=len(prepared.papers),
        page_count=sum(paper.document.metadata.page_count for paper in prepared.papers),
        chunk_count=len(chunks),
        total_chars=sum(lengths),
        mean_chars=round(sum(lengths) / len(lengths), 2),
        min_chars=min(lengths),
        p50_chars=_percentile(lengths, 0.50),
        p95_chars=_percentile(lengths, 0.95),
        max_chars=max(lengths),
        short_chunk_threshold=short_chunk_threshold,
        short_chunk_count=sum(length < short_chunk_threshold for length in lengths),
        oversized_chunk_count=sum(length > chunk_size_chars for length in lengths),
        duplicate_chunk_id_count=len(chunk_ids) - len(set(chunk_ids)),
        missing_required_metadata_count=missing_required,
        section_coverage_ratio=round(
            sum(chunk.section_title is not None for chunk in chunks) / len(chunks), 4
        ),
        papers=paper_stats,
    )


def write_chunk_statistics(stats: CorpusChunkStatistics, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "stats.json").write_text(
        stats.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "chunk_report.md").write_text(
        _build_markdown_report(stats),
        encoding="utf-8",
    )


def _paper_statistics(
    paper_id: str,
    slug: str,
    chunks: tuple[PaperChunk, ...],
) -> PaperChunkStatistics:
    lengths = [len(chunk.text) for chunk in chunks]
    page_count = len({chunk.page_number for chunk in chunks})
    section_count = sum(chunk.section_title is not None for chunk in chunks)
    return PaperChunkStatistics(
        paper_id=paper_id,
        slug=slug,
        page_count=page_count,
        chunk_count=len(chunks),
        mean_chars=round(sum(lengths) / len(lengths), 2),
        min_chars=min(lengths),
        max_chars=max(lengths),
        section_coverage_ratio=round(section_count / len(chunks), 4),
    )


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _build_markdown_report(stats: CorpusChunkStatistics) -> str:
    lines = [
        f"# Agent Seed Corpus v{stats.corpus_version} Chunk 检查报告",
        "",
        f"- Corpus：`{stats.corpus_id}` / v{stats.corpus_version}",
        f"- Chunking：`{stats.chunking_version}`",
        f"- 参数：`{stats.chunk_size_chars} chars / {stats.overlap_chars} overlap`",
        f"- 生成日期：`{stats.generated_on}`",
        f"- 论文 / 页面 / Chunk：{stats.document_count} / {stats.page_count} / {stats.chunk_count}",
        "",
        "## 全局分布",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total chars | {stats.total_chars} |",
        f"| Mean chars | {stats.mean_chars} |",
        f"| Min chars | {stats.min_chars} |",
        f"| P50 chars | {stats.p50_chars} |",
        f"| P95 chars | {stats.p95_chars} |",
        f"| Max chars | {stats.max_chars} |",
        f"| Short chunks (< {stats.short_chunk_threshold}) | {stats.short_chunk_count} |",
        f"| Oversized chunks | {stats.oversized_chunk_count} |",
        f"| Duplicate Chunk IDs | {stats.duplicate_chunk_id_count} |",
        f"| Missing required metadata | {stats.missing_required_metadata_count} |",
        f"| Section coverage | {stats.section_coverage_ratio:.2%} |",
        "",
        "## 逐论文分布",
        "",
        "| Paper | Pages | Chunks | Mean chars | Min | Max | Section coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for paper in stats.papers:
        lines.append(
            f"| {paper.slug} | {paper.page_count} | {paper.chunk_count} | "
            f"{paper.mean_chars} | {paper.min_chars} | {paper.max_chars} | "
            f"{paper.section_coverage_ratio:.2%} |"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- Chunk 不跨页，页码可以直接用于 Citation。",
            "- Section title 由确定性规则识别，覆盖率不等于准确率，需要抽样检查。",
            "- 本报告只描述 Chunk 分布，不包含 Retrieval 指标或策略优劣结论。",
            "",
        ]
    )
    return "\n".join(lines)
