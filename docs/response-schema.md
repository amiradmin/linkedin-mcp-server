# MCP Tool Response Schema

All LinkedIn MCP tools return one of two stable top-level envelopes.

## Success response

```json
{
  "success": true,
  "data": {
    "tool_specific_field": "value"
  },
  "message": "Optional human-readable success message."
}
```

Rules:

- `success` is always `true`.
- `data` is always an object and contains the tool-specific payload.
- `message` is optional and is intended for human-readable confirmation only.
- MCP clients should read structured result values from `data`, not parse `message`.

### Tool-specific success payloads

| Tool | `data` payload |
| --- | --- |
| `linkedin_create_post` | `post_id`, `text` |
| `linkedin_get_profile` | `profile` |
| `linkedin_get_post` | `post` |
| `linkedin_update_post` | `post_id`, `text` |
| `linkedin_delete_post` | `post_id` |

## Error response

```json
{
  "success": false,
  "error": {
    "code": "machine_readable_error_code",
    "message": "Human-readable description.",
    "details": {
      "optional": "structured context"
    }
  }
}
```

Rules:

- `success` is always `false`.
- `error.code` is a stable machine-readable identifier.
- `error.message` is always a human-readable summary.
- `error.details` is optional and contains structured context only.
- Secrets and access tokens must never be exposed in `error.details`.
- Raw exception text is not returned to MCP clients.

## Representative error codes

### Local validation

- `invalid_type`
- `empty_text`
- `text_too_long`
- `invalid_post_urn`
- `invalid_person_urn`

### LinkedIn/API failures

- `linkedin_authentication_error`
- `linkedin_permission_error`
- `linkedin_rate_limit_error`
- `linkedin_request_error`
- `linkedin_server_error`
- `linkedin_unexpected_response`
- `linkedin_timeout`
- `linkedin_network_error`

### Internal failures

- `internal_error`

## Compatibility note

Version `1.2.0` moves all successful tool-specific values under the `data` object. Clients written against earlier versions that read fields such as top-level `post_id`, `text`, `profile`, or `post` should migrate to `response["data"][...]`.
