import json

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
        body = json.loads(request.content)
        assert body["author"] == "urn:li:person:test-user"
        assert body["commentary"] == "Hello from tests"
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:123"})

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_create_post("  Hello from tests  ")

    assert result["success"] is True
    assert result["post_id"] == "urn:li:share:123"
    assert result["text"] == "Hello from tests"


@pytest.mark.asyncio
async def test_create_post_rejects_empty_text(credentials):
    result = await linkedin_server.linkedin_create_post("   ")
    assert result == {
        "success": False,
        "error": {
            "code": "empty_text",
            "message": "Post text cannot be empty or whitespace only.",
        },
    }


@pytest.mark.asyncio
async def test_create_post_rejects_non_string_text(credentials):
    result = await linkedin_server.linkedin_create_post(123)

    assert result["success"] is False
    assert result["error"]["code"] == "invalid_type"
    assert result["error"]["details"]["expected_type"] == "string"


@pytest.mark.asyncio
async def test_create_post_rejects_text_over_max_length(credentials):
    result = await linkedin_server.linkedin_create_post(
        "x" * (linkedin_server.MAX_POST_TEXT_LENGTH + 1)
    )

    assert result["success"] is False
    assert result["error"]["code"] == "text_too_long"
    assert result["error"]["details"] == {
        "max_length": linkedin_server.MAX_POST_TEXT_LENGTH,
        "actual_length": linkedin_server.MAX_POST_TEXT_LENGTH + 1,
    }


@pytest.mark.asyncio
async def test_create_post_does_not_call_linkedin_for_invalid_text(credentials, monkeypatch):
    called = False

    def client(**kwargs):
        nonlocal called
        called = True
        return httpx.AsyncClient(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)

    result = await linkedin_server.linkedin_create_post(" " * 10)

    assert result["success"] is False
    assert result["error"]["code"] == "empty_text"
    assert called is False


@pytest.mark.asyncio
async def test_get_profile_success(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/userinfo"
        return httpx.Response(200, json={"sub": "test-user", "name": "Test User"})

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result["success"] is True
    assert result["profile"]["sub"] == "test-user"


@pytest.mark.asyncio
async def test_get_post_rejects_invalid_urn(credentials):
    result = await linkedin_server.linkedin_get_post("123")
    assert result["success"] is False
    assert "share or ugcPost URN" in result["error"]


@pytest.mark.asyncio
async def test_create_post_maps_authentication_error_and_redacts_token(
    credentials, monkeypatch
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "message": "Expired token test-token",
                "access_token": "test-token",
            },
        )

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_create_post("Hello")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_authentication_error"
    assert result["error"]["details"]["status_code"] == 401
    assert result["error"]["details"]["linkedin_error"]["access_token"] == "[REDACTED]"
    assert "test-token" not in json.dumps(result)


@pytest.mark.asyncio
async def test_get_profile_maps_permission_error(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Insufficient permissions"})

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_permission_error"
    assert result["error"]["details"]["status_code"] == 403


@pytest.mark.asyncio
async def test_create_post_maps_rate_limit_and_retry_after(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "60"},
            json={"message": "Too many requests"},
        )

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_create_post("Hello")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_rate_limit_error"
    assert result["error"]["details"]["retry_after"] == "60"


@pytest.mark.asyncio
async def test_get_profile_maps_linkedin_server_error(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_server_error"
    assert result["error"]["details"]["status_code"] == 503
    assert result["error"]["details"]["linkedin_error"] == "service unavailable"


@pytest.mark.asyncio
async def test_get_post_maps_unexpected_response(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, text="unexpected redirect")

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_get_post("urn:li:share:123")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_unexpected_response"
    assert result["error"]["details"]["status_code"] == 302


@pytest.mark.asyncio
async def test_create_post_maps_timeout(credentials, monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_create_post("Hello")

    assert result == {
        "success": False,
        "error": {
            "code": "linkedin_timeout",
            "message": "The request to LinkedIn timed out.",
        },
    }


@pytest.mark.asyncio
async def test_get_profile_maps_network_error_without_exception_details(
    credentials, monkeypatch
):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "connection failed with secret test-token",
            request=request,
        )

    mock_async_client(monkeypatch, handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result == {
        "success": False,
        "error": {
            "code": "linkedin_network_error",
            "message": "The request to LinkedIn failed due to a network error.",
        },
    }
    assert "test-token" not in json.dumps(result)
