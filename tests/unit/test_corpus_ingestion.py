import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from paper_research_copilot.domain import PaperMetadata, ParsedDocument, ParsedPage
from paper_research_copilot.ingestion import (
    CorpusCatalogLoader,
    CorpusPreparer,
    CorpusValidationError,
    PageAwareChunker,
    PdfParser,
)


def _write_corpus_files(project_root: Path, sha256: str = "a" * 64) -> Path:
    corpus_dir = project_root / "corpus" / "v1"
    corpus_dir.mkdir(parents=True)
    pdf_path = project_root / "data" / "paper.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-test")
    paper = {
        "paper_id": "arxiv:0000.00000",
        "arxiv_id": "0000.00000",
        "arxiv_version": "0000.00000v1",
        "slug": "agent-paper",
        "title": "Canonical Agent Paper",
        "topics": ["agent"],
        "source_url": "https://arxiv.org/pdf/0000.00000v1",
    }
    spec = {
        "corpus_id": "test-corpus",
        "version": 1,
        "created_on": "2026-08-15",
        "description": "Test corpus",
        "papers": [paper],
    }
    manifest = {
        "corpus_id": "test-corpus",
        "corpus_version": 1,
        **paper,
        "local_path": "data/paper.pdf",
        "file_size_bytes": 9,
        "sha256": sha256,
        "page_count": 1,
        "extracted_char_count": 900,
        "parse_status": "verified",
        "warnings": [],
    }
    (corpus_dir / "corpus.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (corpus_dir / "manifest.jsonl").write_text(
        json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return pdf_path


def _document(pdf_path: Path, sha256: str = "a" * 64) -> ParsedDocument:
    return ParsedDocument(
        metadata=PaperMetadata(
            document_sha256=sha256,
            title="PDF filename fallback",
            source_path=str(pdf_path),
            page_count=1,
        ),
        pages=(
            ParsedPage(
                page_number=1,
                text="Abstract\n\nAgent systems use tools and memory. " * 30,
            ),
        ),
    )


def test_corpus_preparer_injects_versioned_chunk_metadata(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    pdf_path = _write_corpus_files(tmp_path)
    catalog = CorpusCatalogLoader(tmp_path).load(1)
    monkeypatch.setattr(PdfParser, "parse", lambda self, path: _document(pdf_path))

    prepared = CorpusPreparer(PdfParser(), PageAwareChunker()).prepare(catalog)

    chunk = prepared.chunks[0]
    assert chunk.corpus_id == "test-corpus"
    assert chunk.paper_id == "arxiv:0000.00000"
    assert chunk.arxiv_version == "0000.00000v1"
    assert chunk.document_sha256 == "a" * 64
    assert chunk.chunking_version == "chunking_v1"
    assert chunk.title == "Canonical Agent Paper"
    assert chunk.source_path == "data/paper.pdf"
    assert chunk.section_title == "Abstract"


def test_corpus_preparer_rejects_sha_mismatch(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    pdf_path = _write_corpus_files(tmp_path)
    catalog = CorpusCatalogLoader(tmp_path).load(1)
    monkeypatch.setattr(
        PdfParser,
        "parse",
        lambda self, path: _document(pdf_path, sha256="b" * 64),
    )

    with pytest.raises(CorpusValidationError, match="SHA-256 differs"):
        CorpusPreparer(PdfParser(), PageAwareChunker()).prepare(catalog)
