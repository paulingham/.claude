---
name: API Patterns
description: REST conventions, pagination, versioning, idempotency, rate limiting, GraphQL N+1, and auth patterns
type: reference
---

# API Patterns

## REST Conventions

### Resource Naming
- Plural nouns for collections: `/users`, `/orders`, `/products`
- Nested resources for ownership: `/users/{id}/orders`
- Avoid verbs in URLs — use HTTP methods for actions
- Actions that don't fit CRUD: `/orders/{id}/cancel` (POST to sub-resource)

### HTTP Methods
| Method | Use | Idempotent? | Safe? |
|--------|-----|-------------|-------|
| GET | Read | Yes | Yes |
| POST | Create | No | No |
| PUT | Replace (full) | Yes | No |
| PATCH | Update (partial) | No | No |
| DELETE | Delete | Yes | No |

### Status Codes
| Code | Meaning | Use When |
|------|---------|----------|
| 200 | OK | Successful read, update, delete |
| 201 | Created | Resource created (include Location header) |
| 204 | No Content | Successful with no body (DELETE) |
| 400 | Bad Request | Invalid input, missing required field |
| 401 | Unauthorized | Not authenticated |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate resource, optimistic lock failure |
| 422 | Unprocessable Content | Validation failure (use over 400 for domain errors) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected failure (never leak internals) |

### Error Envelope
Consistent error format across all endpoints:
```json
{
  "error": {
    "code": "validation_failed",
    "message": "Name is required",
    "details": [
      {"field": "name", "message": "can't be blank"}
    ],
    "correlation_id": "req-abc-123"
  }
}
```

## Pagination

### Cursor-Based (preferred for large datasets)
```json
GET /posts?cursor=eyJpZCI6MTIzfQ&limit=20

{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTQzfQ",
    "has_more": true,
    "limit": 20
  }
}
```
- Stable across inserts/deletes (no row-skipping)
- Cursor = opaque base64 of sort key(s)
- Always include `has_more` flag

### Offset-Based (simple datasets only)
```json
GET /items?page=2&per_page=25

{
  "data": [...],
  "pagination": {
    "total": 847,
    "page": 2,
    "per_page": 25,
    "total_pages": 34
  }
}
```
- Simple to implement and understand
- Breaks on concurrent inserts (items shift pages)
- Cap `per_page` at a maximum (e.g., 100)

## API Versioning

- URI versioning: `/api/v1/users` (simple, cacheable, explicit)
- Header versioning: `Accept: application/vnd.myapi.v1+json` (cleaner URLs)
- Never break existing clients without a deprecation period
- Deprecation headers: `Deprecation: true`, `Sunset: Wed, 01 Jan 2025 00:00:00 GMT`

## Idempotency

For non-idempotent operations (POST):
```
POST /payments
Idempotency-Key: client-generated-uuid-123

{
  "amount": 5000,
  "currency": "USD"
}
```
- Store key → result mapping (expire after 24h)
- Return the same result for duplicate requests
- Prevents double-charge on network retry

## Rate Limiting

Response headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1640995200
Retry-After: 3600  (on 429)
```

Strategies:
- **Fixed window**: simple, but burst at window boundary
- **Sliding window**: smoother, more complex
- **Token bucket**: allows controlled bursts, preferred for APIs
- Store state in Redis for distributed rate limiting

## GraphQL N+1 (DataLoader Pattern)

```typescript
// Anti-pattern: N+1 query per resolver
const resolvers = {
  Post: {
    author: (post) => User.findById(post.authorId)  // N queries!
  }
}

// Pattern: batch with DataLoader
const userLoader = new DataLoader(async (ids) => {
  const users = await User.findAll({ where: { id: ids } });
  return ids.map(id => users.find(u => u.id === id));
});

const resolvers = {
  Post: {
    author: (post) => userLoader.load(post.authorId)  // 1 batched query
  }
}
```

- One DataLoader per request (not global — per-request context)
- DataLoaders batch within a single tick of the event loop
- Cache within the request (not across requests)

## Auth Patterns

### JWT (Stateless)
- Short expiry (15min access token) + long-lived refresh token (7 days)
- Store refresh token in HttpOnly cookie, access token in memory
- Include: `sub` (user id), `iat`, `exp`, `jti` (unique claim id for revocation)
- Rotate refresh tokens on use (detect theft via reuse detection)

### Session (Stateful)
- Store session in Redis with TTL
- Rotate session ID on privilege escalation (login, sudo)
- HttpOnly + Secure + SameSite=Lax cookies
- CSRF token for state-changing requests

### API Key
- Hash the key before storing (never store plaintext)
- Prefix for identification: `sk_live_abc123` (know it's a secret key without revealing it)
- Scope keys to specific permissions
- Audit all API key usage

### OAuth 2.0
- Authorization Code + PKCE for web/mobile (never Implicit flow)
- Client Credentials for service-to-service
- Always validate `state` parameter to prevent CSRF
- Short-lived authorization codes (10 minutes max)
