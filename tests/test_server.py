import asyncio

from src.linkedin_mcp.server import linkedin_create_post, server


def test_mcp_server_exposes_linkedin_create_post():
    tools = asyncio.run(server.list_tools())
    assert any(tool.name == "linkedin_create_post" for tool in tools)


def test_create_post_rejects_empty_text():
    result = asyncio.run(linkedin_create_post("   "))

    assert result["success"] is False
    assert result["error"] == "Post text cannot be empty."
