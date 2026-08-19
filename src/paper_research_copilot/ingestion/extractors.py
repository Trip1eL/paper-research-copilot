"""Interchangeable text extractors for the fast PDF parsing path."""

import re
import time
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

import pymupdf
from pypdf import PdfReader

from paper_research_copilot.domain import PageTextExtraction, ParserName


class PdfExtractionError(RuntimeError):
    """Raised when a fast-path extractor cannot read a PDF."""


class PdfTextExtractor(Protocol):
    @property
    def parser_name(self) -> ParserName: ...

    @property
    def parser_version(self) -> str: ...

    def extract(self, path: Path) -> tuple[PageTextExtraction, ...]: ...


class PypdfExtractor:
    @property
    def parser_name(self) -> ParserName:
        return "pypdf"

    @property
    def parser_version(self) -> str:
        return version("pypdf")

    def extract(self, path: Path) -> tuple[PageTextExtraction, ...]:
        pdf_path = _validated_pdf_path(path)
        try:
            reader = PdfReader(pdf_path)
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise PdfExtractionError(f"Encrypted PDF is not supported: {pdf_path.name}")
            if not reader.pages:
                raise PdfExtractionError(f"PDF contains no pages: {pdf_path.name}")
            results: list[PageTextExtraction] = []
            for page_number, page in enumerate(reader.pages, start=1):
                started = time.perf_counter()
                text = normalize_pdf_text(page.extract_text() or "")
                latency_ms = (time.perf_counter() - started) * 1000
                results.append(
                    PageTextExtraction(
                        page_number=page_number,
                        text=text,
                        parser_name=self.parser_name,
                        parser_version=self.parser_version,
                        latency_ms=round(latency_ms, 2),
                        width=float(page.mediabox.width),
                        height=float(page.mediabox.height),
                        image_count=_pypdf_image_count(page.images),
                    )
                )
            return tuple(results)
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError(f"pypdf failed to extract: {pdf_path.name}") from exc


class PyMuPdfExtractor:
    @property
    def parser_name(self) -> ParserName:
        return "pymupdf"

    @property
    def parser_version(self) -> str:
        return version("PyMuPDF")

    def extract(self, path: Path) -> tuple[PageTextExtraction, ...]:
        pdf_path = _validated_pdf_path(path)
        try:
            with pymupdf.open(pdf_path) as document:  # type: ignore[no-untyped-call]
                if document.needs_pass and not document.authenticate(""):
                    raise PdfExtractionError(f"Encrypted PDF is not supported: {pdf_path.name}")
                if document.page_count == 0:
                    raise PdfExtractionError(f"PDF contains no pages: {pdf_path.name}")
                results: list[PageTextExtraction] = []
                for page_number, page in enumerate(document, start=1):
                    started = time.perf_counter()
                    text = normalize_pdf_text(str(page.get_text("text", sort=True)))
                    latency_ms = (time.perf_counter() - started) * 1000
                    results.append(
                        PageTextExtraction(
                            page_number=page_number,
                            text=text,
                            parser_name=self.parser_name,
                            parser_version=self.parser_version,
                            latency_ms=round(latency_ms, 2),
                            width=float(page.rect.width),
                            height=float(page.rect.height),
                            image_count=len(page.get_images(full=True)),
                        )
                    )
                return tuple(results)
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError(f"PyMuPDF failed to extract: {pdf_path.name}") from exc


def normalize_pdf_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _validated_pdf_path(path: Path) -> Path:
    pdf_path = path.expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PdfExtractionError(f"Expected a PDF file: {pdf_path}")
    return pdf_path


def _pypdf_image_count(images: Sequence[object]) -> int:
    try:
        return len(images)
    except Exception:
        return 0
