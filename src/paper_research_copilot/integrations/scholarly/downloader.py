"""Bounded and validated downloader for trusted academic PDF sources."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from uuid import uuid4

import httpx

from paper_research_copilot.domain import DownloadedPaper, PaperCandidate

ARXIV_HOSTS = frozenset({"arxiv.org", "www.arxiv.org", "export.arxiv.org"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class DownloadValidationError(RuntimeError):
    """Raised when a remote response violates the bounded PDF contract."""


class BoundedPaperDownloader:
    def __init__(
        self,
        asset_root: Path,
        client: httpx.Client | None = None,
        *,
        max_pdf_bytes: int = 50 * 1024 * 1024,
        max_redirects: int = 3,
        timeout: float = 60,
        allowed_hosts: frozenset[str] = ARXIV_HOSTS,
    ) -> None:
        if max_pdf_bytes < 1024:
            raise ValueError("max_pdf_bytes must be at least 1024")
        if max_redirects < 0:
            raise ValueError("max_redirects must not be negative")
        self._asset_root = asset_root.expanduser().resolve()
        self._temporary_root = self._asset_root / ".tmp"
        self._client = client or httpx.Client(
            headers={"User-Agent": "paper-research-copilot/2.0"}
        )
        self._owns_client = client is None
        self._max_pdf_bytes = max_pdf_bytes
        self._max_redirects = max_redirects
        self._timeout = timeout
        self._allowed_hosts = allowed_hosts

    def download(self, candidate: PaperCandidate) -> DownloadedPaper:
        self._temporary_root.mkdir(parents=True, exist_ok=True)
        temporary_path = self._temporary_root / f"{uuid4().hex}.part"
        current_url = candidate.pdf_url
        redirect_count = 0
        try:
            while True:
                _validate_arxiv_pdf_url(current_url, candidate, self._allowed_hosts)
                with self._client.stream(
                    "GET",
                    current_url,
                    follow_redirects=False,
                    timeout=self._timeout,
                ) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise DownloadValidationError(
                                "PDF redirect response is missing Location"
                            )
                        if redirect_count >= self._max_redirects:
                            raise DownloadValidationError("PDF redirect limit exceeded")
                        current_url = urljoin(current_url, location)
                        redirect_count += 1
                        continue
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise DownloadValidationError(
                            f"PDF download failed with HTTP {response.status_code}"
                        ) from exc
                    content_type = response.headers.get("content-type", "")
                    if content_type.partition(";")[0].strip().casefold() != "application/pdf":
                        raise DownloadValidationError(
                            f"Expected application/pdf, received {content_type or 'missing'}"
                        )
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_size = int(content_length)
                        except ValueError as exc:
                            raise DownloadValidationError(
                                "PDF response has invalid Content-Length"
                            ) from exc
                        if declared_size < 0:
                            raise DownloadValidationError(
                                "PDF response has invalid Content-Length"
                            )
                        if declared_size > self._max_pdf_bytes:
                            raise DownloadValidationError(
                                "PDF exceeds configured size limit"
                            )
                    sha256, size = self._write_validated_pdf(response, temporary_path)
                    break

            final_path = self._final_path(candidate, sha256)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            reused = final_path.is_file() and _sha256(final_path) == sha256
            if reused:
                temporary_path.unlink()
            else:
                temporary_path.replace(final_path)
            return DownloadedPaper(
                candidate_id=candidate.identity,
                sha256=sha256,
                local_path=str(final_path),
                file_size_bytes=size,
                content_type="application/pdf",
                downloaded_at=datetime.now(UTC),
                reused_local_file=reused,
            )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def discard(self, downloaded: DownloadedPaper) -> None:
        """Remove an unregistered duplicate while keeping deletion inside asset_root."""

        path = Path(downloaded.local_path).expanduser().resolve()
        try:
            path.relative_to(self._asset_root)
        except ValueError as exc:
            raise DownloadValidationError("Cannot discard a file outside asset_root") from exc
        path.unlink(missing_ok=True)

    def _write_validated_pdf(
        self,
        response: httpx.Response,
        temporary_path: Path,
    ) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        header = bytearray()
        with temporary_path.open("wb") as output:
            for block in response.iter_bytes(chunk_size=64 * 1024):
                if not block:
                    continue
                size += len(block)
                if size > self._max_pdf_bytes:
                    raise DownloadValidationError("PDF exceeds configured size limit")
                if len(header) < 5:
                    header.extend(block[: 5 - len(header)])
                digest.update(block)
                output.write(block)
        if size == 0 or bytes(header) != b"%PDF-":
            raise DownloadValidationError("Downloaded file does not have a valid PDF header")
        return digest.hexdigest(), size

    def _final_path(self, candidate: PaperCandidate, sha256: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", candidate.external_id)
        return (
            self._asset_root
            / candidate.provider
            / safe_id
            / f"v{candidate.revision}-{sha256}.pdf"
        )


def _validate_arxiv_pdf_url(
    value: str,
    candidate: PaperCandidate,
    allowed_hosts: frozenset[str],
) -> None:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in allowed_hosts:
        raise DownloadValidationError("PDF URL must use HTTPS on an allowed arXiv host")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise DownloadValidationError("PDF URL contains unsupported authority components")
    path = unquote(parsed.path).rstrip("/")
    expected = f"/pdf/{candidate.external_id}v{candidate.revision}"
    if path not in {expected, f"{expected}.pdf"}:
        raise DownloadValidationError(
            "PDF URL identity does not match the selected arXiv candidate"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
