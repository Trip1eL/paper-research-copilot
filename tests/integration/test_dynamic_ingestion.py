import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_research_copilot.domain import (
    AcquisitionBudget,
    DocumentParseResult,
    DownloadedPaper,
    PageParseCandidate,
    PageParseResult,
    PageQualityFeatures,
    PageQualityResult,
    PageTextExtraction,
    PaperCandidate,
)
from paper_research_copilot.ingestion import (
    AcademicAcquisitionService,
    DynamicIngestionService,
    PageAwareChunker,
)
from paper_research_copilot.retrieval import QdrantVectorStore
from paper_research_copilot.storage import SqliteResearchRepository

TEXT = (
    "Agent memory systems store verified experience and retrieve it for later attempts. "
    "The mechanism uses bounded retrieval, explicit provenance, and deterministic evaluation. "
) * 4


def _candidate(external_id: str) -> PaperCandidate:
    return PaperCandidate(
        external_id=external_id,
        revision=1,
        title="Durable Agent Memory",
        authors=("Researcher",),
        abstract="A study of persistent memory and bounded retrieval for agents.",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        landing_url=f"https://arxiv.org/abs/{external_id}v1",
        pdf_url=f"https://arxiv.org/pdf/{external_id}v1",
    )


class _Downloader:
    def __init__(self, root: Path, *, content: bytes = b"%PDF-dynamic") -> None:
        self.root = root
        self.content = content
        self.calls = 0
        self.discards = 0

    def download(self, candidate: PaperCandidate) -> DownloadedPaper:
        self.calls += 1
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{candidate.external_id}.pdf"
        path.write_bytes(self.content)
        return DownloadedPaper(
            candidate_id=candidate.identity,
            sha256=hashlib.sha256(self.content).hexdigest(),
            local_path=str(path),
            file_size_bytes=len(self.content),
            content_type="application/pdf",
            downloaded_at=datetime.now(UTC),
        )

    def discard(self, downloaded: DownloadedPaper) -> None:
        self.discards += 1
        Path(downloaded.local_path).unlink(missing_ok=True)


class _Parser:
    def parse(self, path: Path, *, shadow_mode: bool = True) -> DocumentParseResult:
        extraction = PageTextExtraction(
            page_number=1,
            text=TEXT,
            parser_name="pypdf",
            parser_version="test",
            latency_ms=1,
            width=612,
            height=792,
            image_count=0,
        )
        quality = PageQualityResult(
            score=0.95,
            status="accepted",
            features=PageQualityFeatures(
                char_count=len(TEXT),
                line_count=1,
                alphanumeric_ratio=0.9,
                uppercase_word_ratio=0,
                vowelless_word_ratio=0,
                extended_latin_letter_ratio=0,
                control_char_ratio=0,
                replacement_char_ratio=0,
                private_use_char_ratio=0,
                non_printable_char_ratio=0,
                image_count=0,
            ),
        )
        candidate = PageParseCandidate(extraction=extraction, quality=quality)
        page = PageParseResult(
            page_number=1,
            text=TEXT,
            parser_name="pypdf",
            parser_version="test",
            quality_score=0.95,
            quality_status="accepted",
            route_action="primary_accepted",
            selection_reason="Primary extraction passed the test quality gate.",
            candidates=(candidate,),
        )
        return DocumentParseResult(
            document_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_path=str(path),
            page_count=1,
            shadow_mode=shadow_mode,
            parser_versions={"pypdf": "test"},
            total_latency_ms=1,
            accepted_pages=1,
            warning_pages=0,
            quarantined_pages=0,
            secondary_selected_pages=0,
            pages=(page,),
        )


class _Embeddings:
    dimension = 3

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0, 0.0] for _ in texts]


class _Search:
    def __init__(self, candidates: tuple[PaperCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls = 0

    def search(self, query: str, limit: int) -> tuple[PaperCandidate, ...]:
        self.calls += 1
        return self.candidates[:limit]

    def close(self) -> None:
        pass


def _service(repository, downloader, embeddings, store) -> DynamicIngestionService:
    return DynamicIngestionService(
        repository,
        downloader,
        _Parser(),
        PageAwareChunker(chunk_size=400, overlap=40),
        embeddings,
        store,
        max_chunks=20,
        index_version="test-embedding:chunking_v1",
    )


def test_bounded_acquisition_is_persistent_and_idempotent(tmp_path: Path) -> None:
    repository = SqliteResearchRepository(tmp_path / "app.db")
    store = QdrantVectorStore("dynamic", 3, path=tmp_path / "qdrant")
    downloader = _Downloader(tmp_path / "papers")
    embeddings = _Embeddings()
    search = _Search((_candidate("2401.00001"), _candidate("2401.00002")))
    ingestion = _service(repository, downloader, embeddings, store)
    acquisition = AcademicAcquisitionService(
        search,
        ingestion,
        repository,
        budget=AcquisitionBudget(candidates_per_query=5, max_downloads=1),
    )

    first = acquisition.acquire("durable agent memory", task_id="task-1")
    point_count = store.count()
    second = acquisition.acquire("durable agent memory", task_id="task-1")

    assert first.run.status == "succeeded"
    assert first.run.candidate_count == 2
    assert first.run.selected_count == 1
    assert first.run.downloaded_count == 1
    assert first.run.indexed_count == 1
    assert first.ingestions[0].asset.status == "active"
    assert second.run.acquisition_id == first.run.acquisition_id
    assert second.ingestions == ()
    assert downloader.calls == 1
    assert embeddings.calls == 1
    assert store.count() == point_count
    acquisition_id = first.run.acquisition_id
    asset_id = first.ingestions[0].asset.asset_id
    store.close()
    repository.close()

    reopened = SqliteResearchRepository(tmp_path / "app.db")
    assert reopened.get_acquisition(acquisition_id).status == "succeeded"
    assert reopened.get_paper_asset(asset_id).status == "active"
    reopened.close()


def test_sha256_dedup_prevents_second_embedding_and_point_write(tmp_path: Path) -> None:
    repository = SqliteResearchRepository(tmp_path / "app.db")
    store = QdrantVectorStore("dynamic", 3, path=tmp_path / "qdrant")
    downloader = _Downloader(tmp_path / "papers", content=b"%PDF-identical")
    embeddings = _Embeddings()
    service = _service(repository, downloader, embeddings, store)

    first = service.ingest(_candidate("2401.00003"), acquisition_query="agent memory")
    second = service.ingest(_candidate("2401.00004"), acquisition_query="agent memory")

    assert first.outcome == "indexed"
    assert second.outcome == "duplicate"
    assert second.asset.duplicate_of_asset_id == first.asset.asset_id
    assert embeddings.calls == 1
    assert downloader.discards == 1
    assert store.count() == first.asset.chunk_count
    store.close()
    repository.close()


class _CrashAfterQdrant:
    def __init__(self, repository: SqliteResearchRepository) -> None:
        self.repository = repository
        self.failed = False

    def __getattr__(self, name: str):
        return getattr(self.repository, name)

    def mark_asset_indexed(self, *args, **kwargs):
        if not self.failed:
            self.failed = True
            raise RuntimeError("simulated crash after Qdrant commit")
        return self.repository.mark_asset_indexed(*args, **kwargs)


def test_retry_detects_committed_qdrant_points_and_skips_embedding(tmp_path: Path) -> None:
    repository = SqliteResearchRepository(tmp_path / "app.db")
    crashing_repository = _CrashAfterQdrant(repository)
    store = QdrantVectorStore("dynamic", 3, path=tmp_path / "qdrant")
    downloader = _Downloader(tmp_path / "papers")
    embeddings = _Embeddings()
    first_service = _service(crashing_repository, downloader, embeddings, store)
    candidate = _candidate("2401.00005")

    with pytest.raises(RuntimeError, match="simulated crash"):
        first_service.ingest(candidate, acquisition_query="agent memory")
    count_after_crash = store.count()
    second_service = _service(repository, downloader, embeddings, store)
    recovered = second_service.ingest(candidate, acquisition_query="agent memory")

    assert recovered.outcome == "indexed"
    assert recovered.asset.status == "active"
    assert not recovered.embedded
    assert embeddings.calls == 1
    assert downloader.calls == 1
    assert store.count() == count_after_crash
    store.close()
    repository.close()


def test_missing_downloaded_file_is_redownloaded_and_recovers(tmp_path: Path) -> None:
    repository = SqliteResearchRepository(tmp_path / "app.db")
    store = QdrantVectorStore("dynamic", 3, path=tmp_path / "qdrant")
    downloader = _Downloader(tmp_path / "papers")
    embeddings = _Embeddings()
    candidate = _candidate("2401.00006")
    asset = repository.register_candidate(
        candidate,
        acquisition_query="agent memory",
        discovered_at=datetime.now(UTC),
    )
    downloaded = downloader.download(candidate)
    repository.mark_asset_downloaded(asset.asset_id, downloaded)
    Path(downloaded.local_path).unlink()

    recovered = _service(repository, downloader, embeddings, store).ingest(
        candidate,
        acquisition_query="agent memory",
    )

    assert recovered.asset.status == "active"
    assert recovered.downloaded
    assert downloader.calls == 2
    assert embeddings.calls == 1
    store.close()
    repository.close()
