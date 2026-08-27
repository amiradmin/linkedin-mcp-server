from __future__ import annotations

from dataclasses import dataclass
import hmac
import secrets
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx


LINKEDIN_AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
DEFAULT_SCOPES = ("openid", "profile", "w_member_social")
DEFAULT_HTTP_TIMEOUT = 15.0


@dataclass(frozen=True)
class OAuthConfig:
    """Configuration required for LinkedIn's authorization-code flow."""

    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = DEFAULT_SCOPES

    def validate(self) -> None:
        if not self.client_id.strip():
            raise ValueError("LinkedIn client ID is required.")
        if not self.client_secret.strip():
            raise ValueError("LinkedIn client secret is required.")
        if not self.redirect_uri.strip():
            raise ValueError("LinkedIn redirect URI is required.")
        if not self.scopes:
            raise ValueError("At least one LinkedIn OAuth scope is required.")


class OAuthFlowError(RuntimeError):
    """Safe OAuth failure that never embeds credentials in its message."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def generate_state() -> str:
    """Return a cryptographically secure state value for CSRF protection."""

    return secrets.token_urlsafe(32)


def build_authorization_url(
    config: OAuthConfig,
    state: str,
) -> str:
    """Build the LinkedIn authorization URL for one OAuth attempt."""

    config.validate()
    normalized_state = state.strip()
    if not normalized_state:
        raise ValueError("OAuth state is required.")

    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "state": normalized_state,
        "scope": " ".join(config.scopes),
    }
    return f"{LINKEDIN_AUTHORIZATION_URL}?{urlencode(params)}"


def _single_param(params: Mapping[str, Any], name: str) -> str | None:
    value = params.get(name)
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def validate_callback_params(
    params: Mapping[str, Any],
    expected_state: str,
) -> str:
    """Validate a LinkedIn callback and return its authorization code."""

    returned_state = _single_param(params, "state")
    if not returned_state or not hmac.compare_digest(returned_state, expected_state):
        raise OAuthFlowError(
            "invalid_state",
            "LinkedIn OAuth state validation failed.",
        )

    linkedin_error = _single_param(params, "error")
    if linkedin_error:
        if linkedin_error in {"user_cancelled_login", "user_cancelled_authorize", "access_denied"}:
            raise OAuthFlowError(
                "authorization_denied",
                "LinkedIn authorization was denied or cancelled.",
            )
        raise OAuthFlowError(
            "authorization_failed",
            "LinkedIn authorization failed.",
        )

    code = _single_param(params, "code")
    if not code:
        raise OAuthFlowError(
            "missing_authorization_code",
            "LinkedIn did not return an authorization code.",
        )

    return code


async def exchange_authorization_code(
    config: OAuthConfig,
    code: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Exchange a validated LinkedIn authorization code for token data.

    The returned mapping is sensitive and is intended for the credential-storage
    layer. This function deliberately does not print or log request/response data.
    """

    config.validate()
    normalized_code = code.strip()
    if not normalized_code:
        raise OAuthFlowError(
            "missing_authorization_code",
            "LinkedIn authorization code is required.",
        )

    payload = {
        "grant_type": "authorization_code",
        "code": normalized_code,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.redirect_uri,
    }

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=DEFAULT_HTTP_TIMEOUT)

    try:
        try:
            response = await http_client.post(
                LINKEDIN_TOKEN_URL,
                data=payload,
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise OAuthFlowError(
                "token_exchange_timeout",
                "LinkedIn token exchange timed out.",
            ) from exc
        except httpx.RequestError as exc:
            raise OAuthFlowError(
                "token_exchange_network_error",
                "LinkedIn token exchange could not be completed.",
            ) from exc

        if response.status_code >= 400:
            raise OAuthFlowError(
                "token_exchange_rejected",
                "LinkedIn rejected the OAuth token exchange.",
                status_code=response.status_code,
            )

        try:
            token_data = response.json()
        except ValueError as exc:
            raise OAuthFlowError(
                "invalid_token_response",
                "LinkedIn returned an invalid OAuth token response.",
                status_code=response.status_code,
            ) from exc

        if not isinstance(token_data, dict):
            raise OAuthFlowError(
                "invalid_token_response",
                "LinkedIn returned an invalid OAuth token response.",
                status_code=response.status_code,
            )

        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise OAuthFlowError(
                "missing_access_token",
                "LinkedIn OAuth response did not contain an access token.",
                status_code=response.status_code,
            )

        result: dict[str, Any] = {"access_token": access_token}
        for field in (
            "expires_in",
            "refresh_token",
            "refresh_token_expires_in",
            "scope",
            "id_token",
        ):
            if field in token_data:
                result[field] = token_data[field]
        return result
    finally:
        if owns_client:
            await http_client.aclose()


async def complete_oauth_callback(
    config: OAuthConfig,
    params: Mapping[str, Any],
    expected_state: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Validate callback parameters and exchange the code for token data."""

    code = validate_callback_params(params, expected_state)
    return await exchange_authorization_code(config, code, client=client)
