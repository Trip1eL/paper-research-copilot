"""Deterministic page-aware text chunking."""

import re
from uuid import NAMESPACE_URL, uuid5

from paper_research_copilot.domain import ChunkContext, PaperChunk, ParsedDocument

CHUNKING_VERSION = "chunking_v1"


class PageAwareChunker:
    """Split text without crossing page boundaries so citations remain precise."""

    _BOUNDARIES = ("\n\n", ". ", "? ", "! ", "。", "？", "！", "\n", " ")
    _NAMED_SECTIONS = {
        "abstract",
        "acknowledgment",
        "acknowledgments",
        "conclusion",
        "conclusions",
        "introduction",
        "references",
    }
    _NUMBERED_SECTION = re.compile(
        r"^(?P<label>(?:\d+(?:\.\d+)*|[A-Z](?:\.\d+)*))\.?\s+"
        r"(?P<title>[A-Za-z][^\n]{1,100})$"
    )

    def __init__(
        self,
        chunk_size: int = 3200,
        overlap: int = 400,
        chunking_version: str = CHUNKING_VERSION,
    ) -> None:
        if chunk_size < 200:
            raise ValueError("chunk_size must be at least 200 characters")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunking_version = chunking_version

    def split(
        self,
        document: ParsedDocument,
        context: ChunkContext | None = None,
    ) -> tuple[PaperChunk, ...]:
        chunks: list[PaperChunk] = []
        chunk_index = 0
        current_section: str | None = None

        for page in document.pages:
            section_markers = self._section_markers(page.text)
            start = 0
            while start < len(page.text):
                end = self._find_end(page.text, start)
                content_start, content_end = self._trim_bounds(page.text, start, end)
                if content_start < content_end:
                    section_title = self._section_for_chunk(
                        section_markers,
                        current_section,
                        content_start,
                        content_end,
                    )
                    chunk_id = str(
                        uuid5(
                            NAMESPACE_URL,
                            (
                                f"{document.metadata.document_sha256}:"
                                f"{self.chunking_version}:{self.chunk_size}:{self.overlap}:"
                                f"{page.page_number}:{content_start}:{content_end}"
                            ),
                        )
                    )
                    chunks.append(
                        PaperChunk(
                            chunk_id=chunk_id,
                            document_sha256=document.metadata.document_sha256,
                            chunk_index=chunk_index,
                            chunking_version=self.chunking_version,
                            **(context.model_dump() if context else {}),
                            title=document.metadata.title,
                            source_path=document.metadata.source_path,
                            page_number=page.page_number,
                            section_title=section_title,
                            char_start=content_start,
                            char_end=content_end,
                            text=page.text[content_start:content_end],
                        )
                    )
                    chunk_index += 1

                if end >= len(page.text):
                    break
                start = self._align_overlap_start(
                    page.text,
                    max(end - self.overlap, start + 1),
                )

            if section_markers:
                current_section = section_markers[-1][1]

        return tuple(chunks)

    def _find_end(self, text: str, start: int) -> int:
        target = min(start + self.chunk_size, len(text))
        if target == len(text):
            return target

        earliest = start + int(self.chunk_size * 0.65)
        window = text[earliest:target]
        for boundary in self._BOUNDARIES:
            position = window.rfind(boundary)
            if position >= 0:
                return earliest + position + len(boundary)
        return target

    @classmethod
    def _section_markers(cls, text: str) -> tuple[tuple[int, str], ...]:
        markers: list[tuple[int, str]] = []
        offset = 0
        for raw_line in text.splitlines(keepends=True):
            line = re.sub(r"\s+", " ", raw_line).strip()
            section_title = cls._as_section_title(line)
            if section_title:
                markers.append((offset, section_title))
            offset += len(raw_line)
        return tuple(markers)

    @classmethod
    def _as_section_title(cls, line: str) -> str | None:
        if not line or len(line) > 110:
            return None
        if line.casefold() in cls._NAMED_SECTIONS:
            return line

        match = cls._NUMBERED_SECTION.fullmatch(line)
        if not match:
            return None
        title = match.group("title").strip()
        if len(title.split()) > 10 or title.endswith((".", "?", "!")):
            return None
        label = match.group("label")
        letters = [character for character in title if character.isalpha()]
        uppercase_ratio = (
            sum(character.isupper() for character in letters) / len(letters) if letters else 0
        )
        if len(title.split()) > 6 and uppercase_ratio < 0.5:
            return None
        if len(label) == 1 and label.isalpha() and uppercase_ratio < 0.5:
            return None
        return f"{label} {title}"

    def _section_for_chunk(
        self,
        markers: tuple[tuple[int, str], ...],
        previous_section: str | None,
        start: int,
        end: int,
    ) -> str | None:
        section = previous_section
        early_chunk_end = min(end, start + self.overlap + 100)
        for position, title in markers:
            if position <= start or position <= early_chunk_end:
                section = title
            else:
                break
        return section

    @staticmethod
    def _trim_bounds(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    @staticmethod
    def _skip_whitespace(text: str, start: int) -> int:
        while start < len(text) and text[start].isspace():
            start += 1
        return start

    @classmethod
    def _align_overlap_start(cls, text: str, start: int) -> int:
        if 0 < start < len(text) and not text[start - 1].isspace() and not text[start].isspace():
            while start < len(text) and not text[start].isspace():
                start += 1
        return cls._skip_whitespace(text, start)
