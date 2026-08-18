# LinkedIn MCP Server

A lightweight Model Context Protocol (MCP) server that lets an MCP-compatible AI assistant publish public text posts to an authenticated LinkedIn profile.

## Architecture

```text
AI Assistant
     |
     | MCP / stdio
     v
LinkedIn MCP Server
     |
     | HTTPS REST API
     v
LinkedIn
```

## MCP tool

### `linkedin_create_post`

Publishes a public text post to the authenticated LinkedIn profile.

Input:

```json
{
  "text": "Hello from my MCP server 🚀"
}
```

The tool returns the LinkedIn post ID on success.

## Requirements

- Python 3.11+
- A LinkedIn developer application with the required API permissions
- A valid LinkedIn access token
- The authenticated author's LinkedIn person URN

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Credentials

Credentials are intentionally kept outside Git.

Create these files in the project root:

```text
access_token.txt
person_urn.txt
```

`access_token.txt` should contain only the LinkedIn access token.

`person_urn.txt` should contain a value such as:

```text
urn:li:person:YOUR_SUBJECT_ID
```

Set restrictive permissions:

```bash
chmod 600 access_token.txt person_urn.txt
```

Never commit tokens, OAuth credentials, or personal credential files.

## Run the MCP server

```bash
python -m src.linkedin_mcp.server
```

The server uses STDIO, so it intentionally stays running and waits for MCP JSON-RPC messages. Do not print application logs to stdout because stdout is reserved for the MCP protocol.

## MCP Inspector

For local development:

```bash
npx @modelcontextprotocol/inspector \
  python -m src.linkedin_mcp.server
```

Then connect to the STDIO server and call `linkedin_create_post` from the Inspector.

## Testing

Run:

```bash
pytest -q
```

## Security notes

- Secrets are stored in local files ignored by Git.
- `.env.example` contains placeholders only.
- GitHub push protection should remain enabled.
- If a LinkedIn token is ever exposed, revoke/rotate it immediately.

## Portfolio description

> A production-minded MCP server that exposes LinkedIn publishing as a structured AI tool, combining the Model Context Protocol, OAuth-based LinkedIn authentication, secure local credential handling, and REST API integration.
