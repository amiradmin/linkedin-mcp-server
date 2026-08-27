from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server import MCPServer


BASE_DIR = Path(__file__).resolve().parents[2]
ACCESS_TOKEN_FILE = BASE_DIR / "access_token.txt"
PERSON_URN_FILE = BASE_DIR / "person_urn.txt"

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_VERSION = "202601"
MAX_POST_TEXT_LENGTH = 3000

SENSITIVE_ERROR_KEYS = {
    "access_token",
    "authorization",
    "client_secret",
    "refresh_token",
    "token",
}


def read_secret(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Missing secret file: {path}")
    value = path.read_text().strip()
    if not value:
        raise RuntimeError(f"Secret file is empty: {path}")
    return value


def get_access_token() -> str:
    return read_secret(ACCESS_TOKEN_FILE)


def get_person_urn() -> str:
    return read_secret(PERSON_URN_FILE)


def linkedin_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": LINKEDIN_VERSION,
    }


def success_response(
    data: dict[str, Any],
    *,
    message: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "success": True,
        "data": data,
    }
    if message:
        response["message"] = message
    return response


def error_response(code: str, message: str, **details: Any) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        error["details"] = details
    return {
        "success": False,
        "error": error,
    }


def validate_post_text(text: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(text, str):
        return None, error_response(
            "invalid_type",
            "Post text must be a string.",
            expected_type="string",
        )

    normalized_text = text.strip()
    if not normalized_text:
        return None, error_response(
            "empty_text",
            "Post text cannot be empty or whitespace only.",
        )

    if len(normalized_text) > MAX_POST_TEXT_LENGTH:
        return None, error_response(
            "text_too_long",
            f"Post text cannot exceed {MAX_POST_TEXT_LENGTH} characters.",
            max_length=MAX_POST_TEXT_LENGTH,
            actual_length=len(normalized_text),
        )

    return normalized_text, None


def validate_post_urn(post_id: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(post_id, str):
        return None, error_response(
            "invalid_post_urn",
            "post_id must be a LinkedIn share or ugcPost URN.",
        )

    normalized_post_id = post_id.strip()
    if not (
        normalized_post_id.startswith("urn:li:share:")
        or normalized_post_id.startswith("urn:li:ugcPost:")
    ):
        return None, error_response(
            "invalid_post_urn",
            "post_id must be a LinkedIn share or ugcPost URN.",
        )

    return normalized_post_id, None


def redact_sensitive_data(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_ERROR_KEYS or normalized_key.endswith("_token"):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = redact_sensitive_data(item, secrets)
        return sanitized

    if isinstance(value, list):
        return [redact_sensitive_data(item, secrets) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item, secrets) for item in value)

    if isinstance(value, str):
        sanitized_text = value
        for secret in secrets:
            if secret:
                sanitized_text = sanitized_text.replace(secret, "[REDACTED]")
        return sanitized_text

    return value


def linkedin_response_error(
    response: httpx.Response,
    *,
    access_token: str | None = None,
) -> dict[str, Any]:
    try:
        linkedin_error: Any = response.json()
    except (ValueError, TypeError):
        linkedin_error = response.text

    secrets = (access_token,) if access_token else ()
    linkedin_error = redact_sensitive_data(linkedin_error, secrets)

    status_code = response.status_code
    details: dict[str, Any] = {
        "status_code": status_code,
        "linkedin_error": linkedin_error,
    }

    if status_code == 401:
        return error_response(
            "linkedin_authentication_error",
            "LinkedIn authentication failed.",
            **details,
        )

    if status_code == 403:
        return error_response(
            "linkedin_permission_error",
            "LinkedIn denied access to this operation.",
            **details,
        )

    if status_code == 429:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            details["retry_after"] = retry_after
        return error_response(
            "linkedin_rate_limit_error",
            "LinkedIn rate limit exceeded.",
            **details,
        )

    if 400 <= status_code < 500:
        return error_response(
            "linkedin_request_error",
            "LinkedIn rejected the request.",
            **details,
        )

    if 500 <= status_code:
        return error_response(
            "linkedin_server_error",
            "LinkedIn is temporarily unavailable.",
            **details,
        )

    return error_response(
        "linkedin_unexpected_response",
        "LinkedIn returned an unexpected response.",
        **details,
    )


def request_exception_error(exc: httpx.RequestError) -> dict[str, Any]:
    if isinstance(exc, httpx.TimeoutException):
        return error_response(
            "linkedin_timeout",
            "The request to LinkedIn timed out.",
        )

    return error_response(
        "linkedin_network_error",
        "The request to LinkedIn failed due to a network error.",
    )


def unexpected_error() -> dict[str, Any]:
    return error_response(
        "internal_error",
        "An unexpected internal error occurred.",
    )


server = MCPServer(
    name="linkedin-mcp",
    title="LinkedIn MCP",
    description="MCP server for publishing and inspecting LinkedIn posts.",
    version="1.2.0",
)


@server.tool(
    name="linkedin_create_post",
    title="Create LinkedIn Post",
    description="Publish a public text post to the authenticated LinkedIn profile.",
)
async def linkedin_create_post(text: str) -> dict[str, Any]:
    text, error = validate_post_text(text)
    if error:
        return error

    assert text is not None

    try:
        token = get_access_token()
        author = get_person_urn()
        if not author.startswith("urn:li:person:"):
            return error_response(
                "invalid_person_urn",
                "person_urn.txt must contain a LinkedIn person URN.",
            )

        payload = {
            "author": author,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                LINKEDIN_POSTS_URL,
                headers=linkedin_headers(token),
                json=payload,
            )

        if response.status_code == 201:
            return success_response(
                {
                    "post_id": response.headers.get("x-restli-id"),
                    "text": text,
                },
                message="LinkedIn post published successfully.",
            )
        return linkedin_response_error(response, access_token=token)
    except httpx.RequestError as exc:
        return request_exception_error(exc)
    except Exception:
        return unexpected_error()


@server.tool(
    name="linkedin_get_profile",
    title="Get LinkedIn Profile",
    description="Get the authenticated LinkedIn member's OpenID profile information.",
)
async def linkedin_get_profile() -> dict[str, Any]:
    try:
        token = get_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                LINKEDIN_USERINFO_URL,
                headers=linkedin_headers(token),
            )
        if response.status_code == 200:
            return success_response({"profile": response.json()})
        return linkedin_response_error(response, access_token=token)
    except httpx.RequestError as exc:
        return request_exception_error(exc)
    except Exception:
        return unexpected_error()


@server.tool(
    name="linkedin_get_post",
    title="Get LinkedIn Post",
    description="Retrieve a LinkedIn post by its REST post URN.",
)
async def linkedin_get_post(post_id: str) -> dict[str, Any]:
    post_id, post_id_error = validate_post_urn(post_id)
    if post_id_error:
        return post_id_error

    assert post_id is not None

    try:
        token = get_access_token()
        encoded_post_id = quote(post_id, safe="")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{LINKEDIN_POSTS_URL}/{encoded_post_id}",
                headers=linkedin_headers(token),
            )
        if response.status_code == 200:
            return success_response({"post": response.json()})
        return linkedin_response_error(response, access_token=token)
    except httpx.RequestError as exc:
        return request_exception_error(exc)
    except Exception:
        return unexpected_error()


@server.tool(
    name="linkedin_update_post",
    title="Update LinkedIn Post",
    description="Update the commentary text of an existing LinkedIn post.",
)
async def linkedin_update_post(post_id: str, text: str) -> dict[str, Any]:
    post_id, post_id_error = validate_post_urn(post_id)
    if post_id_error:
        return post_id_error

    text, text_error = validate_post_text(text)
    if text_error:
        return text_error

    assert post_id is not None
    assert text is not None

    try:
        token = get_access_token()
        encoded_post_id = quote(post_id, safe="")
        headers = linkedin_headers(token)
        headers["X-RestLi-Method"] = "PARTIAL_UPDATE"
        payload = {
            "patch": {
                "$set": {
                    "commentary": text,
                }
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{LINKEDIN_POSTS_URL}/{encoded_post_id}",
                headers=headers,
                json=payload,
            )

        if response.status_code == 204:
            return success_response(
                {
                    "post_id": post_id,
                    "text": text,
                },
                message="LinkedIn post updated successfully.",
            )
        return linkedin_response_error(response, access_token=token)
    except httpx.RequestError as exc:
        return request_exception_error(exc)
    except Exception:
        return unexpected_error()


@server.tool(
    name="linkedin_delete_post",
    title="Delete LinkedIn Post",
    description="Delete an existing LinkedIn post owned by the authenticated member.",
)
async def linkedin_delete_post(post_id: str) -> dict[str, Any]:
    post_id, post_id_error = validate_post_urn(post_id)
    if post_id_error:
        return post_id_error

    assert post_id is not None

    try:
        token = get_access_token()
        encoded_post_id = quote(post_id, safe="")
        headers = linkedin_headers(token)
        headers["X-RestLi-Method"] = "DELETE"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{LINKEDIN_POSTS_URL}/{encoded_post_id}",
                headers=headers,
            )

        if response.status_code == 204:
            return success_response(
                {"post_id": post_id},
                message="LinkedIn post deleted successfully.",
            )
        return linkedin_response_error(response, access_token=token)
    except httpx.RequestError as exc:
        return request_exception_error(exc)
    except Exception:
        return unexpected_error()


def main() -> None:
    # STDIO is the MCP protocol channel; never print application logs to stdout.
    server.run("stdio")


if __name__ == "__main__":
    main()
