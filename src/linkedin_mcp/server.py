from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer


BASE_DIR = Path(__file__).resolve().parents[2]
ACCESS_TOKEN_FILE = BASE_DIR / "access_token.txt"
PERSON_URN_FILE = BASE_DIR / "person_urn.txt"

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_VERSION = "202601"
MAX_POST_TEXT_LENGTH = 3000


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


def validation_error(code: str, message: str, **details: Any) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"success": False, "error": error}


def validate_post_text(text: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(text, str):
        return None, validation_error(
            "invalid_type",
            "Post text must be a string.",
            expected_type="string",
        )

    normalized_text = text.strip()
    if not normalized_text:
        return None, validation_error(
            "empty_text",
            "Post text cannot be empty or whitespace only.",
        )

    if len(normalized_text) > MAX_POST_TEXT_LENGTH:
        return None, validation_error(
            "text_too_long",
            f"Post text cannot exceed {MAX_POST_TEXT_LENGTH} characters.",
            max_length=MAX_POST_TEXT_LENGTH,
            actual_length=len(normalized_text),
        )

    return normalized_text, None


def response_error(response: httpx.Response) -> dict[str, Any]:
    try:
        error_data: Any = response.json()
    except Exception:
        error_data = response.text
    return {
        "success": False,
        "status_code": response.status_code,
        "error": error_data,
    }


server = MCPServer(
    name="linkedin-mcp",
    title="LinkedIn MCP",
    description="MCP server for publishing and inspecting LinkedIn posts.",
    version="1.1.0",
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
            return validation_error(
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
            return {
                "success": True,
                "message": "LinkedIn post published successfully.",
                "post_id": response.headers.get("x-restli-id"),
                "text": text,
            }
        return response_error(response)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


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
            return {"success": True, "profile": response.json()}
        return response_error(response)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@server.tool(
    name="linkedin_get_post",
    title="Get LinkedIn Post",
    description="Retrieve a LinkedIn post by its REST post URN.",
)
async def linkedin_get_post(post_id: str) -> dict[str, Any]:
    post_id = post_id.strip()
    if not post_id.startswith("urn:li:share:") and not post_id.startswith("urn:li:ugcPost:"):
        return {
            "success": False,
            "error": "post_id must be a LinkedIn share or ugcPost URN.",
        }

    try:
        token = get_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{LINKEDIN_POSTS_URL}/{post_id}",
                headers=linkedin_headers(token),
            )
        if response.status_code == 200:
            return {"success": True, "post": response.json()}
        return response_error(response)
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def main() -> None:
    # STDIO is the MCP protocol channel; never print application logs to stdout.
    server.run("stdio")


if __name__ == "__main__":
    main()
