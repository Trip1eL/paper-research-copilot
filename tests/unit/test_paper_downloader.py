from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from paper_research_copilot.domain import PaperCandidate
from paper_research_copilot.integrations.scholarly import (
    BoundedPaperDownloader,
    DownloadValidationError,
)


def _candidate() -> PaperCandidate:
    return PaperCandidate(
        external_id="2401.01234",
        revision=2,
        title="Bounded Agent Retrieval",
        authors=("Researcher",),
        abstract="A study of bounded retrieval for agents.",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        landing_url="https://arxiv.org/abs/2401.01234v2",
        pdf_url="https://arxiv.org/pdf/2401.01234v2",
    )


def test_downloader_validates_redirect_and_commits_stable_file(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7\n" + b"bounded content" * 20
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.host == "arxiv.org":
            return httpx.Response(
                302,
                headers={"location": "https://export.arxiv.org/pdf/2401.01234v2.pdf"},
                request=request,
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf", "content-length": str(len(pdf))},
            content=pdf,
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = BoundedPaperDownloader(tmp_path / "papers", client)
    first = downloader.download(_candidate())
    second = downloader.download(_candidate())

    assert Path(first.local_path).read_bytes() == pdf
    assert "2401.01234" in first.local_path
    assert first.sha256 in first.local_path
    assert not first.reused_local_file
    assert second.reused_local_file
    assert second.local_path == first.local_path
    assert len(requests) == 4
    assert not tuple((tmp_path / "papers" / ".tmp").glob("*.part"))
    client.close()


def test_downloader_rejects_redirect_to_non_allowlisted_host(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "https://example.com/pdf/2401.01234v2"},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = BoundedPaperDownloader(tmp_path / "papers", client)

    with pytest.raises(DownloadValidationError, match="allowed arXiv host"):
        downloader.download(_candidate())
    assert not tuple((tmp_path / "papers" / ".tmp").glob("*.part"))
    client.close()


@pytest.mark.parametrize(
    ("headers", "content", "error"),
    [
        ({"content-type": "text/html"}, b"%PDF-fake", "application/pdf"),
        ({"content-type": "application/pdf"}, b"not a PDF", "valid PDF header"),
        (
            {"content-type": "application/pdf", "content-length": "2048"},
            b"%PDF-fake",
            "size limit",
        ),
        (
            {"content-type": "application/pdf", "content-length": "invalid"},
            b"%PDF-fake",
            "invalid Content-Length",
        ),
    ],
)
def test_downloader_rejects_invalid_response(
    tmp_path: Path,
    headers: dict[str, str],
    content: bytes,
    error: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, content=content, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = BoundedPaperDownloader(
        tmp_path / "papers",
        client,
        max_pdf_bytes=1024,
    )
    with pytest.raises(DownloadValidationError, match=error):
        downloader.download(_candidate())
    client.close()
