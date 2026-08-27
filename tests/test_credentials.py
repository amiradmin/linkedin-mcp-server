import httpx
import pytest

from src.linkedin_mcp import server as linkedin_server
from src.linkedin_mcp.credentials import (
    CredentialError,
    FileCredentialProvider,
    LinkedInCredentials,
)


def test_file_credential_provider_loads_local_credentials(tmp_path):
    token_file = tmp_path / "access_token.txt"
    urn_file = tmp_path / "person_urn.txt"
    token_file.write_text("  local-token  \n", encoding="utf-8")
    urn_file.write_text("  urn:li:person:local-user  \n", encoding="utf-8")

    provider = FileCredentialProvider(token_file, urn_file)

    assert provider.get_credentials() == LinkedInCredentials(
        access_token="local-token",
        person_urn="urn:li:person:local-user",
    )


def test_file_credential_provider_missing_file_error_does_not_expose_secret(tmp_path):
    token_file = tmp_path / "missing-token.txt"
    urn_file = tmp_path / "person_urn.txt"
    urn_file.write_text("urn:li:person:test-user", encoding="utf-8")

    provider = FileCredentialProvider(token_file, urn_file)

    with pytest.raises(CredentialError) as exc_info:
        provider.get_credentials()

    message = str(exc_info.value)
    assert "Missing LinkedIn access token credential file." == message
    assert str(token_file) not in message


def test_file_credential_provider_empty_secret_error_is_safe(tmp_path):
    token_file = tmp_path / "access_token.txt"
    urn_file = tmp_path / "person_urn.txt"
    token_file.write_text("   \n", encoding="utf-8")
    urn_file.write_text("urn:li:person:test-user", encoding="utf-8")

    provider = FileCredentialProvider(token_file, urn_file)

    with pytest.raises(CredentialError) as exc_info:
        provider.get_credentials()

    assert str(exc_info.value) == "The LinkedIn access token credential file is empty."


@pytest.mark.asyncio
async def test_mcp_tool_uses_injected_credential_provider(monkeypatch):
    class ProductionLikeProvider:
        def get_credentials(self) -> LinkedInCredentials:
            return LinkedInCredentials(
                access_token="provider-token",
                person_urn="urn:li:person:provider-user",
            )

    original_async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer provider-token"
        return httpx.Response(200, json={"sub": "provider-user"})

    def client(**kwargs):
        return original_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr(httpx, "AsyncClient", client)
    linkedin_server.set_credential_provider(ProductionLikeProvider())
    try:
        result = await linkedin_server.linkedin_get_profile()
    finally:
        linkedin_server.set_credential_provider(None)

    assert result == {
        "success": True,
        "data": {"profile": {"sub": "provider-user"}},
    }


@pytest.mark.asyncio
async def test_mcp_tool_returns_safe_credential_error(monkeypatch):
    class FailingProvider:
        def get_credentials(self) -> LinkedInCredentials:
            raise CredentialError("Credential backend is unavailable.")

    called = False

    def client(**kwargs):
        nonlocal called
        called = True
        return httpx.AsyncClient(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    linkedin_server.set_credential_provider(FailingProvider())
    try:
        result = await linkedin_server.linkedin_get_profile()
    finally:
        linkedin_server.set_credential_provider(None)

    assert result == {
        "success": False,
        "error": {
            "code": "credential_error",
            "message": "Credential backend is unavailable.",
        },
    }
    assert called is False
