from typing import Any

import httpx
from pytest import MonkeyPatch

from paper_research_copilot.integrations.openai_compatible import OpenAICompatibleTransport


class _FakeClient:
    calls = 0

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.__class__.calls += 1
        if self.calls == 1:
            raise httpx.ConnectError("temporary disconnect")
        return httpx.Response(
            200,
            json={"data": "ok"},
            request=httpx.Request("POST", url),
        )


def test_transport_retries_transient_network_failure(monkeypatch: MonkeyPatch) -> None:
    _FakeClient.calls = 0
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    transport = OpenAICompatibleTransport(
        "https://provider.example/v1",
        "secret",
        max_attempts=2,
        retry_backoff=0,
    )

    response = transport.post("embeddings", {"input": ["query"]})

    assert response == {"data": "ok"}
    assert _FakeClient.calls == 2
