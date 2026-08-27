from urllib.parse import parse_qs, urlparse

import httpx
import pytest

import linkedin_oauth
from src.linkedin_mcp.oauth import (
    DEFAULT_SCOPES,
    LINKEDIN_TOKEN_URL,
    OAuthConfig,
    OAuthFlowError,
    build_authorization_url,
    complete_oauth_callback,
    exchange_authorization_code,
    generate_state,
    validate_callback_params,
)


@pytest.fixture
def oauth_config() -> OAuthConfig:
    return OAuthConfig(
        client_id="test-client-id",
        client_secret="super-secret-client-value",
        redirect_uri="http://localhost:8000/callback",
    )


def test_build_authorization_url_uses_required_parameters(oauth_config):
    url = build_authorization_url(oauth_config, "csrf-state")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.linkedin.com"
    assert parsed.path == "/oauth/v2/authorization"
    assert query == {
        "response_type": ["code"],
        "client_id": ["test-client-id"],
        "redirect_uri": ["http://localhost:8000/callback"],
        "state": ["csrf-state"],
        "scope": [" ".join(DEFAULT_SCOPES)],
    }


def test_generate_state_returns_unpredictable_non_empty_values():
    first = generate_state()
    second = generate_state()

    assert len(first) >= 32
    assert len(second) >= 32
    assert first != second


def test_validate_callback_returns_code_for_matching_state():
    code = validate_callback_params(
        {"state": ["expected-state"], "code": ["authorization-code"]},
        "expected-state",
    )

    assert code == "authorization-code"


def test_validate_callback_rejects_mismatched_state():
    with pytest.raises(OAuthFlowError) as exc_info:
        validate_callback_params(
            {"state": ["attacker-state"], "code": ["authorization-code"]},
            "expected-state",
        )

    assert exc_info.value.code == "invalid_state"
    assert "authorization-code" not in str(exc_info.value)


def test_validate_callback_maps_denied_consent_safely():
    with pytest.raises(OAuthFlowError) as exc_info:
        validate_callback_params(
            {
                "state": ["expected-state"],
                "error": ["user_cancelled_authorize"],
                "error_description": ["private provider details"],
            },
            "expected-state",
        )

    assert exc_info.value.code == "authorization_denied"
    assert "private provider details" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_exchange_authorization_code_posts_expected_form(oauth_config):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == LINKEDIN_TOKEN_URL
        body = parse_qs(request.content.decode("utf-8"))
        assert body == {
            "grant_type": ["authorization_code"],
            "code": ["authorization-code"],
            "client_id": ["test-client-id"],
            "client_secret": ["super-secret-client-value"],
            "redirect_uri": ["http://localhost:8000/callback"],
        }
        return httpx.Response(
            200,
            json={
                "access_token": "access-token-value",
                "expires_in": 5184000,
                "scope": "openid profile w_member_social",
                "extra_provider_field": "ignored",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await exchange_authorization_code(
            oauth_config,
            "authorization-code",
            client=client,
        )

    assert result == {
        "access_token": "access-token-value",
        "expires_in": 5184000,
        "scope": "openid profile w_member_social",
    }


@pytest.mark.asyncio
async def test_complete_callback_does_not_exchange_code_for_invalid_state(oauth_config):
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"access_token": "should-not-be-used"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OAuthFlowError) as exc_info:
            await complete_oauth_callback(
                oauth_config,
                {"state": ["wrong-state"], "code": ["authorization-code"]},
                "expected-state",
                client=client,
            )

    assert exc_info.value.code == "invalid_state"
    assert called is False


@pytest.mark.asyncio
async def test_token_exchange_failure_does_not_leak_secrets(oauth_config, capsys):
    authorization_code = "very-sensitive-authorization-code"
    provider_access_token = "provider-returned-secret-token"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": "invalid_request",
                "error_description": (
                    f"code={authorization_code} "
                    f"secret={oauth_config.client_secret} "
                    f"token={provider_access_token}"
                ),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OAuthFlowError) as exc_info:
            await exchange_authorization_code(
                oauth_config,
                authorization_code,
                client=client,
            )

    captured = capsys.readouterr()
    visible = captured.out + captured.err + str(exc_info.value)

    assert exc_info.value.code == "token_exchange_rejected"
    assert exc_info.value.status_code == 401
    assert authorization_code not in visible
    assert oauth_config.client_secret not in visible
    assert provider_access_token not in visible


def test_local_oauth_helper_rejects_production_callback_url():
    with pytest.raises(RuntimeError, match="local loopback"):
        linkedin_oauth.local_server_address(
            "https://example.com/oauth/linkedin/callback"
        )


def test_callback_request_logging_is_disabled(capsys):
    handler = object.__new__(linkedin_oauth.CallbackHandler)
    handler.log_message(
        '"GET /callback?code=secret-code&state=secret-state HTTP/1.1" 200 -'
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
