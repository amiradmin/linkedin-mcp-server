import asyncio

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


def mock_async_client(monkeypatch, handler):
    original_async_client = httpx.AsyncClient

    def client(**kwargs):
        return original_async_client(
            transport=httpx.MockTransport(handler), **kwargs
        )

    monkeypatch.setattr(httpx, "AsyncClient", client)


def test_mcp_server_exposes_delete_post_tool():
    tools = asyncio.run(linkedin_server.server.list_tools())
    names = {tool.name for tool in tools}
    assert "linkedin_delete_post" in names


@pytest.mark.asyncio
async def test_delete_post_success(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["x-restli-method"] == "DELETE"
        assert request.url.raw_path == b"/rest/posts/urn%3Ali%3Ashare%3A123"
        return httpx.Response(204)

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_delete_post("  urn:li:share:123  ")

    assert result == {
        "success": True,
        "message": "LinkedIn post deleted successfully.",
        "post_id": "urn:li:share:123",
    }


@pytest.mark.asyncio
async def test_delete_post_rejects_invalid_urn_without_api_call(credentials, monkeypatch):
    called = False

    def client(**kwargs):
        nonlocal called
        called = True
        return httpx.AsyncClient(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)

    result = await linkedin_server.linkedin_delete_post("123")

    assert result["success"] is False
    assert result["error"]["code"] == "invalid_post_urn"
    assert called is False


@pytest.mark.asyncio
async def test_delete_post_maps_permission_error(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "Post cannot be deleted by this member"},
        )

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_delete_post("urn:li:ugcPost:456")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_permission_error"
    assert result["error"]["details"]["status_code"] == 403


@pytest.mark.asyncio
async def test_delete_post_maps_network_error(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_delete_post("urn:li:share:789")

    assert result == {
        "success": False,
        "error": {
            "code": "linkedin_network_error",
            "message": "The request to LinkedIn failed due to a network error.",
        },
    }
