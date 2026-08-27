# Delete LinkedIn Post

The MCP server exposes `linkedin_delete_post` for deleting an existing LinkedIn post owned by the authenticated member.

## Input

```json
{
  "post_id": "urn:li:share:1234567890"
}
```

Supported post identifiers are:

- `urn:li:share:...`
- `urn:li:ugcPost:...`

Invalid identifiers are rejected locally before any request is sent to LinkedIn.

## LinkedIn API behavior

The tool URL-encodes the post URN and calls:

```text
DELETE /rest/posts/{encodedPostUrn}
```

with the required LinkedIn headers, including:

```text
X-RestLi-Method: DELETE
X-Restli-Protocol-Version: 2.0.0
LinkedIn-Version: YYYYMM
```

A successful deletion returns HTTP `204 No Content`.

LinkedIn documents post deletion as idempotent: deleting a previously deleted UGC post also returns `204`. Batch deletion is not supported.

## Errors

Authentication, permission, rate-limit, LinkedIn request/server, timeout, and network failures use the server's structured error handling. LinkedIn enforces ownership and permissions for the target post.
