"""Small OpenAI-compatible HTTP transport shared by model providers."""

import time
from collections.abc import Mapping
from typing import Any

import httpx


class OpenAICompatibleTransport:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 60.0,
        max_attempts: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Max attempts must be at least 1")
        if retry_backoff < 0:
            raise ValueError("Retry backoff must not be negative")
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._retry_backoff = retry_backoff

    def post(self, resource: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._post_once(resource, payload)
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                if not retryable or attempt == self._max_attempts:
                    raise
            except httpx.TransportError:
                if attempt == self._max_attempts:
                    raise
            time.sleep(self._retry_backoff * (2 ** (attempt - 1)))
        raise RuntimeError("Provider retry loop exhausted unexpectedly")

    def _post_once(self, resource: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        last_response: httpx.Response | None = None
        with httpx.Client(timeout=self._timeout) as client:
            for url in self._candidate_urls(resource):
                response = client.post(url, headers=self._headers, json=payload)
                last_response = response
                if response.status_code != httpx.codes.NOT_FOUND:
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ValueError("Provider returned a non-object JSON response")
                    return data

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("Provider request did not return a response")

    def _candidate_urls(self, resource: str) -> tuple[str, ...]:
        clean_resource = resource.lstrip("/")
        if self._base_url.endswith("/v1"):
            return (f"{self._base_url}/{clean_resource}",)
        return (
            f"{self._base_url}/{clean_resource}",
            f"{self._base_url}/v1/{clean_resource}",
        )
