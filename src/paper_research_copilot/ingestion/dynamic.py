"""Quality-gated and idempotent ingestion into the mutable dynamic collection."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from paper_research_copilot.domain import (
    ChunkContext,
    DocumentParseResult,
    DownloadedPaper,
    DynamicIngestionResult,
    DynamicParseSummary,
    PaperAsset,
    PaperCandidate,
    PaperChunk,
    PaperMetadata,
)
from paper_research_copilot.ingestion.chunker import PageAwareChunker
from paper_research_copilot.ingestion.router import build_indexable_document
from paper_research_copilot.integrations import EmbeddingProvider
from paper_research_copilot.storage import AcquisitionRepository


class PaperDownloader(Protocol):
    def download(self, candidate: PaperCandidate) -> DownloadedPaper: ...

    def discard(self, downloaded: DownloadedPaper) -> None: ...


class DynamicDocumentParser(Protocol):
    def parse(self, path: Path, *, shadow_mode: bool = True) -> DocumentParseResult: ...


class DynamicVectorStore(Protocol):
    @property
    def collection_name(self) -> str: ...

    def replace_by_metadata(
        self,
        chunks: Sequence[PaperChunk],
        vectors: Sequence[Sequence[float]],
        metadata: dict[str, str | int | bool],
    ) -> None: ...

    def count(self, metadata: dict[str, str | int | bool] | None = None) -> int: ...

    def get_vectors(self, chunk_ids: Sequence[str]) -> dict[str, tuple[float, ...]]: ...


class DynamicIngestionService:
    def __init__(
        self,
        repository: AcquisitionRepository,
        downloader: PaperDownloader,
        parser: DynamicDocumentParser,
        chunker: PageAwareChunker,
        embeddings: EmbeddingProvider,
        vector_store: DynamicVectorStore,
        *,
        max_chunks: int = 500,
        index_version: str = "bge-m3:chunking_v1",
    ) -> None:
        if max_chunks < 1:
            raise ValueError("max_chunks must be at least one")
        self._repository = repository
        self._downloader = downloader
        self._parser = parser
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._max_chunks = max_chunks
        self._index_version = index_version

    def ingest(
        self,
        candidate: PaperCandidate,
        *,
        acquisition_query: str,
    ) -> DynamicIngestionResult:
        asset = self._repository.register_candidate(
            candidate,
            acquisition_query=acquisition_query,
            discovered_at=_now(),
        )
        if asset.status == "active":
            return DynamicIngestionResult(
                asset=asset,
                outcome="already_active",
                embedded=False,
            )
        if asset.status == "duplicate":
            return DynamicIngestionResult(asset=asset, outcome="duplicate", embedded=False)
        if asset.status == "indexed":
            active = self._repository.activate_asset(asset.asset_id, updated_at=_now())
            return DynamicIngestionResult(asset=active, outcome="indexed", embedded=False)

        if asset.status not in {"discovered", "download_failed"} and not _valid_local_asset(
            asset
        ):
            asset = self._repository.mark_asset_failed(
                asset.asset_id,
                status="download_failed",
                error="Persisted dynamic PDF is missing or has changed",
                updated_at=_now(),
            )

        download_attempted = asset.status in {"discovered", "download_failed"}
        downloaded = self._download(asset)
        if downloaded is None:
            return self._failed(asset.asset_id, downloaded=download_attempted)
        duplicate = self._repository.find_paper_asset_by_sha256(downloaded.sha256)
        if duplicate is not None and duplicate.asset_id != asset.asset_id:
            self._downloader.discard(downloaded)
            duplicated = self._repository.mark_asset_duplicate(
                asset.asset_id,
                duplicate_of_asset_id=duplicate.asset_id,
                updated_at=_now(),
            )
            return DynamicIngestionResult(
                asset=duplicated,
                outcome="duplicate",
                downloaded=download_attempted,
                embedded=False,
            )
        if asset.status in {"discovered", "download_failed"}:
            asset = self._repository.mark_asset_downloaded(asset.asset_id, downloaded)

        parsed = self._parse_and_chunk(asset, downloaded)
        if parsed is None:
            return self._failed(asset.asset_id, downloaded=download_attempted)
        asset, chunks = parsed
        if asset.status == "indexed":
            active = self._repository.activate_asset(asset.asset_id, updated_at=_now())
            return DynamicIngestionResult(
                asset=active,
                outcome="indexed",
                downloaded=download_attempted,
                embedded=False,
            )

        existing_vectors = self._vector_store.get_vectors(
            [chunk.chunk_id for chunk in chunks]
        )
        embedded = False
        if len(existing_vectors) != len(chunks):
            try:
                vectors = self._embeddings.embed([chunk.text for chunk in chunks])
                metadata = _asset_metadata(asset, self._chunker.chunking_version)
                self._vector_store.replace_by_metadata(chunks, vectors, metadata)
                if self._vector_store.count(metadata) != len(chunks):
                    raise RuntimeError("Dynamic Qdrant point count does not match chunk count")
                embedded = True
            except Exception as exc:
                failed = self._repository.mark_asset_failed(
                    asset.asset_id,
                    status="indexing_failed",
                    error=_public_error(exc),
                    updated_at=_now(),
                )
                return DynamicIngestionResult(
                    asset=failed,
                    outcome="failed",
                    downloaded=download_attempted,
                    embedded=embedded,
                )

        indexed = self._repository.mark_asset_indexed(
            asset.asset_id,
            chunk_count=len(chunks),
            collection_name=self._vector_store.collection_name,
            index_version=self._index_version,
            updated_at=_now(),
        )
        active = self._repository.activate_asset(indexed.asset_id, updated_at=_now())
        return DynamicIngestionResult(
            asset=active,
            outcome="indexed",
            downloaded=download_attempted,
            embedded=embedded,
        )

    def _download(self, asset: PaperAsset) -> DownloadedPaper | None:
        if asset.status not in {"discovered", "download_failed"}:
            if asset.sha256 is None or asset.local_path is None or asset.file_size_bytes is None:
                raise RuntimeError("Persisted downloaded asset is missing file provenance")
            return DownloadedPaper(
                candidate_id=asset.candidate.identity,
                sha256=asset.sha256,
                local_path=asset.local_path,
                file_size_bytes=asset.file_size_bytes,
                content_type="application/pdf",
                downloaded_at=asset.updated_at,
                reused_local_file=True,
            )
        try:
            return self._downloader.download(asset.candidate)
        except Exception as exc:
            self._repository.mark_asset_failed(
                asset.asset_id,
                status="download_failed",
                error=_public_error(exc),
                updated_at=_now(),
            )
            return None

    def _parse_and_chunk(
        self,
        asset: PaperAsset,
        downloaded: DownloadedPaper,
    ) -> tuple[PaperAsset, tuple[PaperChunk, ...]] | None:
        try:
            routed = self._parser.parse(Path(downloaded.local_path), shadow_mode=False)
            metadata = PaperMetadata(
                document_sha256=downloaded.sha256,
                title=asset.candidate.title,
                authors=asset.candidate.authors,
                source_path=downloaded.local_path,
                page_count=routed.page_count,
            )
            document = build_indexable_document(metadata, routed)
            summary = DynamicParseSummary(
                document_sha256=routed.document_sha256,
                page_count=routed.page_count,
                accepted_pages=routed.accepted_pages,
                warning_pages=routed.warning_pages,
                quarantined_pages=routed.quarantined_pages,
                secondary_selected_pages=routed.secondary_selected_pages,
                parser_versions={
                    str(name): version
                    for name, version in routed.parser_versions.items()
                },
            )
            if asset.status in {"downloaded", "quarantined"}:
                asset = self._repository.mark_asset_parsed(
                    asset.asset_id,
                    page_count=routed.page_count,
                    parse_summary_json=summary.model_dump_json(),
                    updated_at=_now(),
                )
            context = ChunkContext(
                corpus_id="paper-dynamic",
                corpus_version=1,
                paper_id=asset.asset_id,
                arxiv_id=asset.candidate.external_id,
                arxiv_version=(
                    f"{asset.candidate.external_id}v{asset.candidate.revision}"
                ),
            )
            chunks = self._chunker.split(document, context)
            if not chunks:
                raise ValueError("Dynamic PDF produced no indexable chunks")
            if len(chunks) > self._max_chunks:
                raise ValueError(
                    f"Dynamic PDF produced {len(chunks)} chunks; limit is {self._max_chunks}"
                )
            return asset, chunks
        except Exception as exc:
            status: Literal["quarantined", "indexing_failed"] = (
                "indexing_failed"
                if asset.status in {"parsed", "indexing_failed"}
                else "quarantined"
            )
            self._repository.mark_asset_failed(
                asset.asset_id,
                status=status,
                error=_public_error(exc),
                updated_at=_now(),
            )
            return None

    def _failed(self, asset_id: str, *, downloaded: bool) -> DynamicIngestionResult:
        return DynamicIngestionResult(
            asset=self._repository.get_paper_asset(asset_id),
            outcome="failed",
            downloaded=downloaded,
            embedded=False,
        )


def _asset_metadata(
    asset: PaperAsset,
    chunking_version: str,
) -> dict[str, str | int | bool]:
    if asset.sha256 is None:
        raise RuntimeError("Cannot index an asset without SHA-256")
    return {
        "corpus_id": "paper-dynamic",
        "paper_id": asset.asset_id,
        "document_sha256": asset.sha256,
        "chunking_version": chunking_version,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_local_asset(asset: PaperAsset) -> bool:
    if asset.sha256 is None or asset.local_path is None or asset.file_size_bytes is None:
        return False
    path = Path(asset.local_path)
    return (
        path.is_file()
        and path.stat().st_size == asset.file_size_bytes
        and _sha256(path) == asset.sha256
    )


def _public_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now() -> datetime:
    return datetime.now(UTC)
