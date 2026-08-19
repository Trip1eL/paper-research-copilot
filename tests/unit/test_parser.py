from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from paper_research_copilot.ingestion import PdfParser


def _write_text_pdf(path: Path, *, include_metadata: bool = True) -> None:
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
    if include_metadata:
        writer.add_metadata({"/Title": "Agent Systems", "/Author": "Ada; Bob"})
    with path.open("wb") as output:
        writer.write(output)


def test_parser_extracts_text_and_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "agent-systems.pdf"
    _write_text_pdf(pdf_path)

    document = PdfParser().parse(pdf_path)

    assert document.metadata.title == "Agent Systems"
    assert document.metadata.authors == ("Ada", "Bob")
    assert document.metadata.page_count == 1
    assert len(document.metadata.document_sha256) == 64
    assert document.pages[0].page_number == 1
    assert "Agent systems use tools and memory" in document.pages[0].text


def test_parser_falls_back_to_filename_when_title_cannot_be_inferred(tmp_path: Path) -> None:
    pdf_path = tmp_path / "fallback-name.pdf"
    _write_text_pdf(pdf_path, include_metadata=False)

    document = PdfParser().parse(pdf_path)

    assert document.metadata.title == "fallback-name"


def test_parser_infers_uppercase_title_lines() -> None:
    title = PdfParser._choose_title(
        None,
        "Published as a conference paper\nAGENT RESEARCH\nSYSTEMS\nAda Lovelace\nABSTRACT",
        "fallback",
    )

    assert title == "AGENT RESEARCH SYSTEMS"
