# LinkedIn MCP Server

A lightweight Model Context Protocol (MCP) server that lets an MCP-compatible AI assistant publish and manage public text posts on an authenticated LinkedIn profile.

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

## MCP tools

### `linkedin_create_post`

Publishes a public text post to the authenticated LinkedIn profile.

Input:

```json
{
  "text": "Hello from my MCP server 🚀"
}
```

The tool returns the LinkedIn post ID on success.

### `linkedin_get_profile`

Returns the authenticated member's OpenID profile information.

### `linkedin_get_post`

Retrieves a LinkedIn post by a `urn:li:share:...` or `urn:li:ugcPost:...` identifier.

### `linkedin_update_post`

Updates the commentary text of an existing LinkedIn post.

Input:

```json
{
  "post_id": "urn:li:share:1234567890",
  "text": "Updated post text"
}
```

The server validates the post URN and text locally, then uses LinkedIn's Posts API `PARTIAL_UPDATE` operation. LinkedIn enforces ownership and permission rules; permission failures are returned as structured MCP errors.

### `linkedin_delete_post`

Deletes a LinkedIn post by its share or UGC post URN. See `docs/delete-post.md` for API behavior and idempotency details.

## Response schema

All MCP tools use one stable response contract.

Successful calls return:

```json
{
  "success": true,
  "data": {
    "tool_specific_field": "value"
  },
  "message": "Optional success message"
}
```

Failures return:

```json
{
  "success": false,
  "error": {
    "code": "machine_readable_code",
    "message": "Human-readable description",
    "details": {}
  }
}
```

`data` contains the tool-specific payload. `message` and `error.details` are optional. See `docs/response-schema.md` for the complete contract and migration notes.

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

MCP tools obtain credentials through a `CredentialProvider` abstraction rather than reading secrets directly. The default local-development provider remains file-based for backward compatibility.

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

Production deployments can install a secret-manager-backed provider without changing any MCP tool implementation. Never commit tokens, OAuth credentials, or personal credential files. See `docs/credentials.md` for the provider contract, production integration pattern, and secret-handling rules.

## OAuth design

The production authentication design uses LinkedIn's 3-legged authorization-code flow with the minimum scopes required by the current tools:

```text
openid profile w_member_social
```

Local development uses a loopback callback, while production requires an HTTPS callback and server-side secret storage. See `docs/oauth-flow.md` for the flow diagram, token lifecycle, failure states, and security requirements.

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

Then connect to the STDIO server and call the LinkedIn tools from the Inspector.

## Testing

Run:

```bash
pytest -q
```

Tests use fake credentials, reusable `httpx.MockTransport` fixtures, sanitized LinkedIn response samples, and an automatic guard that blocks real HTTP. No LinkedIn secrets or live API access are required. See `docs/testing.md` for the fixture and network-isolation strategy.

## Security notes

- MCP tools access secrets only through the credential-provider interface.
- Local credential files are ignored by Git and should use restrictive permissions.
- `.env.example` contains placeholders only.
- GitHub push protection should remain enabled.
- LinkedIn API errors are sanitized before they are returned to MCP clients.
- If a LinkedIn token is ever exposed, revoke/rotate it immediately.

For responsible vulnerability reporting, see [SECURITY.md](SECURITY.md).

## Contributing & collaboration

Focused bug fixes, tests, documentation improvements, MCP tool improvements, OAuth/security hardening, and API integration improvements are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) before starting a substantial change.

For broader backend, AI/MCP, open-source, or industrial-AI collaboration, visit [Amir Behvandi's GitHub profile](https://github.com/amiradmin) or join [ForgeMind Discussions](https://github.com/amiradmin/ForgeMind/discussions).

English and Persian participation are both welcome.

## Portfolio description

> A production-minded MCP server that exposes LinkedIn publishing and post management as structured AI tools, combining the Model Context Protocol, OAuth-based LinkedIn authentication, secure credential-provider abstraction, and REST API integration.
