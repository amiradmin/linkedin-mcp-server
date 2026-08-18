import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer


BASE_DIR = Path(__file__).resolve().parents[2]

ACCESS_TOKEN_FILE = BASE_DIR / "access_token.txt"
PERSON_URN_FILE = BASE_DIR / "person_urn.txt"

LINKEDIN_API_URL = "https://api.linkedin.com/rest/posts"


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


server = MCPServer(
    name="linkedin-mcp",
    title="LinkedIn MCP",
    description="MCP server for publishing posts to LinkedIn.",
    version="1.0.0",
)


@server.tool(
    name="linkedin_create_post",
    title="Create LinkedIn Post",
    description="Publish a public text post to the authenticated LinkedIn profile.",
)
async def linkedin_create_post(text: str) -> dict[str, Any]:
    """
    Create a public text post on LinkedIn.
    """

    text = text.strip()

    if not text:
        return {
            "success": False,
            "error": "Post text cannot be empty.",
        }

    try:
        access_token = get_access_token()
        author = get_person_urn()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202601",
        }

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
                LINKEDIN_API_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code == 201:
            post_id = response.headers.get("x-restli-id")

            return {
                "success": True,
                "message": "LinkedIn post published successfully.",
                "post_id": post_id,
                "text": text,
            }

        try:
            error_data = response.json()
        except Exception:
            error_data = response.text

        return {
            "success": False,
            "status_code": response.status_code,
            "error": error_data,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def main() -> None:
    # IMPORTANT:
    # MCP STDIO uses stdout for the protocol.
    # Never print/log anything to stdout.

    server.run("stdio")


if __name__ == "__main__":
    main()