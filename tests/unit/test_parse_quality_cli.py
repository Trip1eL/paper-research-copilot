from pathlib import Path

import pytest
from pypdf import PdfWriter

from paper_research_copilot.cli import main


def test_inspect_parse_quality_shows_both_candidates_and_fallback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with pdf_path.open("wb") as output:
        writer.write(output)

    exit_code = main(["inspect-parse-quality", str(pdf_path), "--page", "1"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Parse Quality Shadow" in output
    assert "pypdf==" in output
    assert "pymupdf==" in output
    assert "structured_fallback_required" in output
