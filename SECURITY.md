# Security Policy

Security is especially important in this project because it interacts with OAuth credentials and authenticated LinkedIn APIs.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for vulnerabilities involving credentials, authentication, authorization, token exposure, or sensitive user data.

Report security issues privately by email:

**amirbehvandi747@gmail.com**

Include enough information to reproduce and understand the issue, but do not send live access tokens, passwords, client secrets, or other reusable credentials.

Useful details include:

- Affected component or MCP tool
- Expected and observed behavior
- Reproduction steps using sanitized values
- Potential impact
- Suggested mitigation, if known

## Credential handling

Contributors and users should follow these rules:

- Never commit LinkedIn access tokens or OAuth client secrets.
- Never paste live credentials into issues or pull requests.
- Keep local credential files outside version control.
- Use restrictive filesystem permissions for local secret files.
- Use placeholders in examples and documentation.
- Use sanitized API fixtures in tests.
- Rotate or revoke a credential immediately if exposure is suspected.

## Testing security-sensitive changes

Changes involving OAuth, credential providers, HTTP requests, authorization, or response sanitization should include automated tests where practical.

The test suite must not make real LinkedIn API calls.

## Supported code

Security fixes should target the current `main` branch unless a separately maintained release branch is explicitly documented in the repository.
