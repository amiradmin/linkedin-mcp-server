from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
import pytest

from src.linkedin_mcp import server as linkedin_server
from src.linkedin_mcp.credentials import LinkedInCredentials


FAKE_ACCESS_TOKEN = "test-token"
FAKE_PERSON_URN = "urn:li:person:test-user"
FIXTURE_DIR = Path(__file__).parent / "fixtures"


class FakeCredentialProvider:
    """In-memory provider used by tests so real credentials are never required."""

    def __init__(self, credentials: LinkedInCredentials) -> None:
        self._credentials = credentials

    def get_credentials(self) -> LinkedInCredentials:
        return self._credentials


@pytest.fixture
def fake_credentials() -> LinkedInCredentials:
    return LinkedInCredentials(
        access_token=FAKE_ACCESS_TOKEN,
        person_urn=FAKE_PERSON_URN,
    )


@pytest.fixture
def credentials(fake_credentials: LinkedInCredentials):
    """Install isolated fake LinkedIn credentials for one test."""

    linkedin_server.set_credential_provider(FakeCredentialProvider(fake_credentials))
    try:
        yield fake_credentials
    finally:
        linkedin_server.set_credential_provider(None)


@pytest.fixture(scope="session")
def linkedin_responses() -> dict[str, Any]:
    """Representative LinkedIn API payloads captured as sanitized test data."""

    path = FIXTURE_DIR / "linkedin_responses.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def linkedin_http_mock(monkeypatch):
    """Install an httpx MockTransport-backed AsyncClient for LinkedIn tool tests."""

    original_async_client = httpx.AsyncClient

    def install(
        handler: Callable[[httpx.Request], Awaitable[httpx.Response] | httpx.Response],
    ) -> None:
        def client(**kwargs: Any) -> httpx.AsyncClient:
            kwargs.pop("transport", None)
            return original_async_client(
                transport=httpx.MockTransport(handler),
                **kwargs,
            )

        monkeypatch.setattr(httpx, "AsyncClient", client)

    return install


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    """Fail immediately if any test reaches httpx's real async network transport."""

    async def blocked_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Real HTTP is disabled in tests: {request.method} {request.url.host}"
        )

    monkeypatch.setattr(
        httpx.AsyncHTTPTransport,
        "handle_async_request",
        blocked_request,
    )
