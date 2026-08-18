import httpx
import pytest

from src.linkedin_mcp import server as linkedin_server


@pytest.fixture
def credentials(tmp_path, monkeypatch):
    token_file = tmp_path / "access_token.txt"
    urn_file = tmp_path / "person_urn.txt"
    token_file.write_text("test-token")
    urn_file.write_text("urn:li:person:test-user")
    monkeypatch.setattr(linkedin_server, "ACCESS_TOKEN_FILE", token_file)
    monkeypatch.setattr(linkedin_server, "PERSON_URN_FILE", urn_file)


def test_mcp_server_exposes_expected_tools():
    import asyncio

    tools = asyncio.run(linkedin_server.server.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "linkedin_create_post",
        "linkedin_get_profile",
        "linkedin_get_post",
    } <= names


@pytest.mark.asyncio
async def test_create_post_success(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer test-token"
        body = request.json()
        assert body["author"] == "urn:li:person:test-user"
        assert body["commentary"] == "Hello from tests"
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:123"})

    def client(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)

    result = await linkedin_server.linkedin_create_post("  Hello from tests  ")

    assert result["success"] is True
    assert result["post_id"] == "urn:li:share:123"
    assert result["text"] == "Hello from tests"


@pytest.mark.asyncio
async def test_create_post_rejects_empty_text(credentials):
    result = await linkedin_server.linkedin_create_post("   ")
    assert result == {"success": False, "error": "Post text cannot be empty."}


@pytest.mark.asyncio
async def test_get_profile_success(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/userinfo"
        return httpx.Response(200, json={"sub": "test-user", "name": "Test User"})

    def client(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)

    result = await linkedin_server.linkedin_get_profile()

    assert result["success"] is True
    assert result["profile"]["sub"] == "test-user"


@pytest.mark.asyncio
async def test_get_post_rejects_invalid_urn(credentials):
    result = await linkedin_server.linkedin_get_post("123")
    assert result["success"] is False
    assert "share or ugcPost URN" in result["error"]
