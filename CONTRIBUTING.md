# Contributing to LinkedIn MCP Server

Thanks for your interest in contributing.

This project aims to keep LinkedIn integrations small, testable, secure, and easy to use from MCP-compatible AI clients.

## Ways to contribute

Useful contributions include:

- Bug reports with reproducible steps
- Tests for LinkedIn API edge cases
- Improvements to OAuth and credential handling
- MCP tool improvements
- Documentation and setup improvements
- Error handling and response-schema improvements
- Security hardening

## Before starting a larger change

For substantial changes, open an issue first and describe:

1. The problem you want to solve
2. The proposed behavior
3. Any LinkedIn API permissions or scopes involved
4. Security implications
5. How the change will be tested

Small documentation fixes and focused bug fixes can be submitted directly.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the test suite:

```bash
pytest -q
```

Tests must not make real LinkedIn API calls. Use the project's mocked HTTP transport and sanitized fixtures.

## Security requirements

Never commit or include any of the following in issues, tests, fixtures, examples, screenshots, or pull requests:

- LinkedIn access tokens
- OAuth client secrets
- Personal credential files
- Private API responses containing sensitive data
- Real user credentials

Use placeholders and sanitized fixtures only.

If you discover a security vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Pull requests

Please keep pull requests focused and include:

- A clear description of the change
- Tests for new behavior when applicable
- Updated documentation for user-facing behavior
- No unrelated formatting or refactoring

Before submitting, run:

```bash
pytest -q
```

## Collaboration

Technical discussions and focused contributions are welcome in English or Persian.

For broader AI, backend, MCP, or open-source collaboration, you can also visit [Amir Behvandi's GitHub profile](https://github.com/amiradmin) or [ForgeMind Discussions](https://github.com/amiradmin/ForgeMind/discussions).
