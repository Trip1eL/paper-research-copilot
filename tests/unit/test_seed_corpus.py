from pathlib import Path

import pytest

from paper_research_copilot.domain import PaperMetadata, ParsedDocument, ParsedPage
from scripts import build_seed_corpus


def _corpus_spec() -> dict[str, object]:
    return {"corpus_id": "test-corpus", "version": 1}


def _paper_spec() -> dict[str, object]:
    return {
        "paper_id": "arxiv:0000.00000",
        "arxiv_id": "0000.00000",
        "arxiv_version": "0000.00000v1",
        "slug": "test-paper",
        "title": "Agent Research",
        "topics": ["agent"],
        "source_url": "https://arxiv.org/pdf/0000.00000v1",
    }


def test_page_metrics_detect_control_characters() -> None:
    metrics = build_seed_corpus._page_metrics("useful text\x03")

    assert metrics["char_count"] == 12
    assert metrics["control_ratio"] > 0
    assert metrics["replacement_ratio"] == 0


def test_title_matching_ignores_case_spacing_and_punctuation() -> None:
    expected = "ReAct: Synergizing Reasoning and Acting"
    extracted = "REAC T: S YNERGIZING REASONING AND ACTING\nAuthors"

    assert build_seed_corpus._title_appears_on_first_page(expected, extracted)
    assert build_seed_corpus._title_similarity("Agent Research", "agent-research") == 1


def test_missing_pdf_produces_failed_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_seed_corpus, "PROJECT_ROOT", tmp_path)
    record = build_seed_corpus._verify_paper(
        _corpus_spec(), _paper_spec(), tmp_path / "missing.pdf"
    )

    assert record["parse_status"] == "failed"
    assert record["warnings"] == ["缺少 PDF 文件；请使用 --download 下载"]


def test_suspicious_page_produces_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(build_seed_corpus, "PROJECT_ROOT", tmp_path)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    document = ParsedDocument(
        metadata=PaperMetadata(
            document_sha256="a" * 64,
            title="Agent Research",
            authors=(),
            source_path=str(pdf_path),
            page_count=1,
        ),
        pages=(ParsedPage(page_number=1, text="Agent Research" + "\x03" * 2),),
    )
    monkeypatch.setattr(build_seed_corpus.PdfParser, "parse", lambda self, path: document)

    record = build_seed_corpus._verify_paper(_corpus_spec(), _paper_spec(), pdf_path)

    assert record["parse_status"] == "warning"
    assert record["suspicious_pages"] == [1]
