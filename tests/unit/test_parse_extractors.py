from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from paper_research_copilot.ingestion import PyMuPdfExtractor, PypdfExtractor


def _write_text_pdf(path: Path) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Agent systems use tools and memory.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as output:
        writer.write(output)


def test_fast_extractors_preserve_page_identity_and_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    _write_text_pdf(pdf_path)

    pypdf_page = PypdfExtractor().extract(pdf_path)[0]
    pymupdf_page = PyMuPdfExtractor().extract(pdf_path)[0]

    assert pypdf_page.page_number == pymupdf_page.page_number == 1
    assert pypdf_page.parser_name == "pypdf"
    assert pymupdf_page.parser_name == "pymupdf"
    assert "Agent systems use tools and memory" in pypdf_page.text
    assert "Agent systems use tools and memory" in pymupdf_page.text
    assert pypdf_page.width == pymupdf_page.width == 612
    assert pypdf_page.height == pymupdf_page.height == 792
