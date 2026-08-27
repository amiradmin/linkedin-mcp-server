# Testing strategy

The test suite must never call LinkedIn over the public network or depend on real credentials.

## Shared fixtures

`tests/conftest.py` provides reusable fixtures for LinkedIn-facing tests:

- `credentials`: installs an in-memory credential provider with fake values.
- `fake_credentials`: exposes the fake `LinkedInCredentials` value when assertions need it.
- `linkedin_http_mock`: replaces `httpx.AsyncClient` with a `MockTransport`-backed client for one test.
- `linkedin_responses`: loads sanitized representative API payloads from `tests/fixtures/linkedin_responses.json`.
- `block_real_http`: an automatic network guard that fails the test if httpx reaches its real async transport.

## Representative responses

The checked-in response fixture contains sanitized examples for:

- successful profile retrieval
- successful post retrieval
- authentication failure
- permission failure
- rate limiting
- LinkedIn server failure

These values are test data only. No payload may contain a real LinkedIn access token, person identifier, authorization code, or client secret.

## Example

```python
@pytest.mark.asyncio
async def test_profile(credentials, linkedin_http_mock, linkedin_responses):
    async def handler(request):
        return httpx.Response(200, json=linkedin_responses["profile_success"])

    linkedin_http_mock(handler)
    result = await linkedin_server.linkedin_get_profile()

    assert result["success"] is True
```

## Network isolation

The autouse `block_real_http` fixture patches `httpx.AsyncHTTPTransport.handle_async_request`. Tests using `httpx.MockTransport` continue to work normally, but any accidental attempt to use the default network transport raises an assertion immediately.

This is intentional: a passing test suite is evidence that no LinkedIn API request escaped the test process.

## Rules for new tests

- Use fake credentials only.
- Use `linkedin_http_mock` or an explicitly constructed `httpx.MockTransport`.
- Add sanitized response examples to the shared fixture file instead of copying provider payloads repeatedly.
- Never disable the real-network guard to make a test pass.
- Never require LinkedIn developer secrets in local tests or CI.
