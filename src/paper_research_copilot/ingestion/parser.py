"""Page-aware PDF parsing for text-based academic papers."""

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

from paper_research_copilot.domain import PaperMetadata, ParsedDocument, ParsedPage


class PdfParsingError(RuntimeError):
    """Raised when a PDF cannot provide usable text."""


class PdfParser:
    """Extract ordered page text and stable document metadata from a PDF."""

    def parse(self, path: Path) -> ParsedDocument:
        pdf_path = path.expanduser().resolve()
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise PdfParsingError(f"Expected a PDF file: {pdf_path}")

        try:
            reader = PdfReader(pdf_path)
        except Exception as exc:
            raise PdfParsingError(f"Failed to open PDF: {pdf_path.name}") from exc

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PdfParsingError(f"Encrypted PDF is not supported: {pdf_path.name}") from exc

        if not reader.pages:
            raise PdfParsingError(f"PDF contains no pages: {pdf_path.name}")

        pages = tuple(
            ParsedPage(
                page_number=page_number,
                text=self._normalize_text(page.extract_text() or ""),
            )
            for page_number, page in enumerate(reader.pages, start=1)
        )
        if not any(page.text for page in pages):
            raise PdfParsingError(
                f"PDF contains no extractable text: {pdf_path.name}. "
                "Scanned PDFs require OCR and are outside the first-version scope."
            )

        raw_metadata = reader.metadata
        raw_title = raw_metadata.title if raw_metadata else None
        title = self._choose_title(raw_title, pages[0].text, pdf_path.stem)
        author_text = (raw_metadata.author if raw_metadata else None) or ""
        authors = tuple(part.strip() for part in author_text.split(";") if part.strip())

        metadata = PaperMetadata(
            document_sha256=self._sha256(pdf_path),
            title=title.strip(),
            authors=authors,
            source_path=str(pdf_path),
            page_count=len(pages),
        )
        return ParsedDocument(metadata=metadata, pages=pages)

    @classmethod
    def _choose_title(cls, raw_title: str | None, first_page_text: str, fallback: str) -> str:
        if raw_title and raw_title.strip().lower() not in {"untitled", "unknown"}:
            return raw_title.strip()

        candidates: list[str] = []
        for line in first_page_text.splitlines()[:20]:
            line = line.strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith(("published as", "arxiv:", "preprint")):
                continue
            if line.upper() == "ABSTRACT":
                break
            letters = [character for character in line if character.isalpha()]
            uppercase_ratio = (
                sum(character.isupper() for character in letters) / len(letters) if letters else 0
            )
            if uppercase_ratio >= 0.7:
                candidates.append(line)
                if len(candidates) == 3:
                    break
                continue
            if candidates:
                break
            return fallback

        if not candidates:
            return fallback
        title = " ".join(candidates)
        title = re.sub(r"\b([A-Z]) ([A-Z]{2,})\b", r"\1\2", title)
        title = re.sub(r"\b([A-Z]{2,}) ([A-Z])(?=[:;,\.\s])", r"\1\2", title)
        return title

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
