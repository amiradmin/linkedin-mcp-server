import json

import httpx
import pytest

from src.linkedin_mcp import server as linkedin_server


@pytest.mark.asyncio
async def test_profile_success_uses_shared_response_fixture(
    credentials,
    linkedin_http_mock,
    linkedin_responses,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/userinfo"
        assert request.headers["authorization"] == "Bearer test-token"
        return httpx.Response(200, json=linkedin_responses["profile_success"])

    linkedin_http_mock(handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result == {
        "success": True,
        "data": {"profile": linkedin_responses["profile_success"]},
    }


@pytest.mark.asyncio
async def test_authentication_fixture_is_sanitized_before_return(
    credentials,
    linkedin_http_mock,
    linkedin_responses,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json=linkedin_responses["authentication_error"],
        )

    linkedin_http_mock(handler)

    result = await linkedin_server.linkedin_create_post("Hello from tests")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_authentication_error"
    assert result["error"]["details"]["linkedin_error"]["access_token"] == "[REDACTED]"
    assert "test-token" not in json.dumps(result)


@pytest.mark.asyncio
async def test_rate_limit_fixture_preserves_retry_after(
    credentials,
    linkedin_http_mock,
    linkedin_responses,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "60"},
            json=linkedin_responses["rate_limit_error"],
        )

    linkedin_http_mock(handler)

    result = await linkedin_server.linkedin_create_post("Hello")

    assert result["success"] is False
    assert result["error"]["code"] == "linkedin_rate_limit_error"
    assert result["error"]["details"]["retry_after"] == "60"


@pytest.mark.asyncio
async def test_network_failure_mock_returns_stable_error(
    credentials,
    linkedin_http_mock,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection failure", request=request)

    linkedin_http_mock(handler)

    result = await linkedin_server.linkedin_get_profile()

    assert result == {
        "success": False,
        "error": {
            "code": "linkedin_network_error",
            "message": "The request to LinkedIn failed due to a network error.",
        },
    }


@pytest.mark.asyncio
async def test_validation_failure_never_needs_http(credentials):
    result = await linkedin_server.linkedin_create_post("   ")

    assert result == {
        "success": False,
        "error": {
            "code": "empty_text",
            "message": "Post text cannot be empty or whitespace only.",
        },
    }


@pytest.mark.asyncio
async def test_real_http_transport_is_blocked_by_default():
    async with httpx.AsyncClient() as client:
        with pytest.raises(AssertionError, match="Real HTTP is disabled in tests"):
            await client.get("https://api.linkedin.com/v2/userinfo")
