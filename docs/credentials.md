# Credential providers

The MCP tools do not read LinkedIn secrets directly. They request a `LinkedInCredentials` value through the `CredentialProvider` protocol in `src/linkedin_mcp/credentials.py`.

## Architecture

```text
MCP tool
   |
   v
get_credentials()
   |
   v
CredentialProvider
   |
   +--> FileCredentialProvider (local development)
   |
   +--> future secret-manager provider (production)
```

A provider returns:

```python
LinkedInCredentials(
    access_token="...",
    person_urn="urn:li:person:...",
)
```

The tools only depend on this contract. A production provider can therefore be installed with `set_credential_provider(...)` without modifying publishing, profile, update, retrieval, or delete tool code.

## Local development

The default provider remains file-based for backward compatibility. It reads these files from the project root:

```text
access_token.txt
person_urn.txt
```

Recommended permissions on Linux/macOS:

```bash
chmod 600 access_token.txt person_urn.txt
```

Only the account running the MCP server should be able to read these files. Do not place them in shared directories, container images, source-control commits, test fixtures containing real values, or build artifacts.

Both files are stripped of leading/trailing whitespace when loaded. Missing, unreadable, or empty files raise a safe `CredentialError`; secret contents are never included in the exception message.

## Production integration

Implement the `CredentialProvider` protocol and return `LinkedInCredentials` from the production secret store. For example, an adapter may read from HashiCorp Vault, AWS Secrets Manager, Google Secret Manager, Azure Key Vault, or another platform-managed credential service.

The MCP tool layer must not know which backend is used. Install the provider during application startup:

```python
from src.linkedin_mcp import server

server.set_credential_provider(MySecretManagerProvider(...))
```

The provider should fetch only the credentials needed by this service, use the platform's least-privilege identity, and avoid writing secrets to local disk unless the deployment explicitly requires it.

## Secret-handling rules

- Never log access tokens, refresh tokens, authorization codes, client secrets, or raw provider responses containing credentials.
- Never return credentials in MCP response payloads or error details.
- Keep real secrets out of Git and `.env.example`.
- Restrict local credential files to the service account (`0600` is recommended).
- Rotate or revoke a LinkedIn token immediately if it is exposed.
- Prefer platform-managed secret stores for production deployments.
- Keep credential-provider exceptions generic and free of secret values.

## Testing

Tests should use temporary files or fake/in-memory provider implementations. They must never call real LinkedIn APIs or contain real LinkedIn credentials.
