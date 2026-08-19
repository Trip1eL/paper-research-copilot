"""Load and prepare a versioned paper corpus for deterministic ingestion."""

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from paper_research_copilot.domain import (
    ChunkContext,
    CorpusCatalog,
    CorpusManifestRecord,
    CorpusPaperAsset,
    CorpusSpec,
    PaperChunk,
    ParsedDocument,
)
from paper_research_copilot.ingestion.chunker import PageAwareChunker
from paper_research_copilot.ingestion.parser import PdfParser


class CorpusValidationError(ValueError):
    """Raised when versioned corpus files or local PDFs are inconsistent."""


@dataclass(frozen=True)
class PreparedPaper:
    asset: CorpusPaperAsset
    document: ParsedDocument
    chunks: tuple[PaperChunk, ...]


@dataclass(frozen=True)
class PreparedCorpus:
    catalog: CorpusCatalog
    papers: tuple[PreparedPaper, ...]

    @property
    def chunks(self) -> tuple[PaperChunk, ...]:
        return tuple(chunk for paper in self.papers for chunk in paper.chunks)


class CorpusCatalogLoader:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root.resolve()

    def load(self, version: int) -> CorpusCatalog:
        corpus_dir = self._project_root / "corpus" / f"v{version}"
        spec_path = corpus_dir / "corpus.json"
        manifest_path = corpus_dir / "manifest.jsonl"
        try:
            spec = CorpusSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
            records = tuple(
                CorpusManifestRecord.model_validate(json.loads(line))
                for line in manifest_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        except FileNotFoundError as exc:
            raise CorpusValidationError(f"Corpus file is missing: {exc.filename}") from exc
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorpusValidationError(f"Corpus metadata is invalid: {exc}") from exc

        if spec.version != version:
            raise CorpusValidationError(
                f"Requested corpus v{version}, but spec declares v{spec.version}"
            )
        records_by_paper = {record.paper_id: record for record in records}
        expected_ids = {paper.paper_id for paper in spec.papers}
        if len(records_by_paper) != len(records):
            raise CorpusValidationError("Manifest contains duplicate paper_id values")
        if set(records_by_paper) != expected_ids:
            raise CorpusValidationError("Corpus spec and manifest paper sets do not match")

        assets: list[CorpusPaperAsset] = []
        for paper in spec.papers:
            record = records_by_paper[paper.paper_id]
            self._validate_record(spec, paper.paper_id, paper.arxiv_version, record)
            pdf_path = (self._project_root / record.local_path).resolve()
            if not pdf_path.is_relative_to(self._project_root):
                raise CorpusValidationError(f"Corpus PDF escapes project root: {record.local_path}")
            if not pdf_path.is_file():
                raise CorpusValidationError(f"Corpus PDF is missing: {record.local_path}")
            assets.append(CorpusPaperAsset(spec=paper, manifest=record, pdf_path=pdf_path))
        return CorpusCatalog(spec=spec, papers=tuple(assets))

    @staticmethod
    def _validate_record(
        spec: CorpusSpec,
        paper_id: str,
        arxiv_version: str,
        record: CorpusManifestRecord,
    ) -> None:
        if record.corpus_id != spec.corpus_id or record.corpus_version != spec.version:
            raise CorpusValidationError(f"Manifest corpus identity mismatch for {paper_id}")
        if record.arxiv_version != arxiv_version:
            raise CorpusValidationError(f"Manifest arXiv revision mismatch for {paper_id}")
        if record.parse_status == "failed":
            raise CorpusValidationError(f"Cannot ingest failed Parse record: {paper_id}")


class CorpusPreparer:
    def __init__(self, parser: PdfParser, chunker: PageAwareChunker) -> None:
        self._parser = parser
        self._chunker = chunker

    def prepare(self, catalog: CorpusCatalog) -> PreparedCorpus:
        papers: list[PreparedPaper] = []
        for asset in catalog.papers:
            document = self._parser.parse(asset.pdf_path)
            if document.metadata.document_sha256 != asset.manifest.sha256:
                raise CorpusValidationError(
                    f"PDF SHA-256 differs from manifest: {asset.spec.paper_id}"
                )
            portable_metadata = document.metadata.model_copy(
                update={
                    "title": asset.spec.title,
                    "source_path": asset.manifest.local_path,
                }
            )
            document = document.model_copy(update={"metadata": portable_metadata})
            context = ChunkContext(
                corpus_id=catalog.spec.corpus_id,
                corpus_version=catalog.spec.version,
                paper_id=asset.spec.paper_id,
                arxiv_id=asset.spec.arxiv_id,
                arxiv_version=asset.spec.arxiv_version,
            )
            chunks = self._chunker.split(document, context)
            if not chunks:
                raise CorpusValidationError(f"PDF produced no chunks: {asset.spec.paper_id}")
            papers.append(PreparedPaper(asset=asset, document=document, chunks=chunks))
        return PreparedCorpus(catalog=catalog, papers=tuple(papers))
