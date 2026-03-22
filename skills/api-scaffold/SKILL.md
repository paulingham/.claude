---
name: "API Scaffold"
description: "Generate API endpoints from spec: route definitions, controllers, request/response validation, error handling, pagination, rate limiting. OpenAPI-driven or convention-based."
context: fork
agent: software-engineer
argument-hint: "Resource name or OpenAPI spec path (e.g., 'users' or 'openapi.yaml')"
---

# API Scaffold

## What This Skill Does

Generates a complete API resource layer: route definitions, controllers/handlers, request validation, response serialization, error handling, pagination, and rate limiting middleware. Follows REST conventions by default, supports GraphQL where the project uses it.

## When to Invoke

- Adding a new API resource/endpoint
- Scaffolding multiple CRUD endpoints from a data model
- Implementing pagination, filtering, or sorting on existing endpoints
- Adding rate limiting or request validation middleware
- Generating OpenAPI documentation from existing routes

## Process

### Step 1: Determine API Style

| Signal | API Style |
|--------|-----------|
| `express`, `fastify`, `koa` in deps | REST (Node.js) |
| `config/routes.rb` | REST (Rails) |
| `urls.py` | REST (Django) |
| `gin`, `echo`, `chi` in imports | REST (Go) |
| `type-graphql`, `@nestjs/graphql` | GraphQL |
| `apollo-server`, `graphql-yoga` | GraphQL |
| Existing OpenAPI/Swagger spec | REST (spec-driven) |

### Step 2: Define Resource Contract

For each resource, define the contract before generating code:

```markdown
## Resource: [name]

### Endpoints
- POST   /api/v1/[resources]          → Create
- GET    /api/v1/[resources]          → List (paginated)
- GET    /api/v1/[resources]/:id      → Show
- PATCH  /api/v1/[resources]/:id      → Update
- DELETE /api/v1/[resources]/:id      → Soft delete

### Request/Response
- Create: { field1: string, field2: number } → 201 { id, field1, field2, created_at }
- List:   ?page=1&per_page=20&sort=created_at&order=desc → 200 { data: [...], meta: { page, per_page, total, total_pages } }
- Show:   → 200 { id, field1, field2, created_at, updated_at }
- Update: { field1?: string } → 200 { id, field1, field2, updated_at }
- Delete: → 204 No Content

### Validation Rules
- field1: required, string, max 255 chars
- field2: required, integer, min 0
```

### Step 3: Generate Endpoint Code

Follow the project's existing patterns. If no patterns exist, use these conventions:

#### Controller/Handler Pattern (all stacks)
```
1. Parse and validate request input
2. Authenticate the caller (verify token/session)
3. Authorize the action (RBAC check — does this role have permission?)
4. Authorize the resource (object-level — does this user own/have access to THIS specific resource?)
5. Call service/use-case layer (never put business logic in controller)
6. Serialize response
7. Return with appropriate status code
```

**Object-level authorization (critical):** Never trust the client-provided ID alone. Always verify the authenticated user owns or is permitted to access the specific resource: `user.id == record.owner_id` or `record.tenant_id == user.tenant_id`. Scope database queries by the authenticated user's permissions — never fetch by ID without an ownership check.

#### Status Code Convention
| Action | Success | Client Error | Not Found |
|--------|---------|-------------|-----------|
| Create | 201 Created | 422 Unprocessable | — |
| List | 200 OK | 400 Bad Request | — |
| Show | 200 OK | — | 404 Not Found |
| Update | 200 OK | 422 Unprocessable | 404 Not Found |
| Delete | 204 No Content | — | 404 Not Found |

#### Error Response Format (consistent across all endpoints)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      { "field": "email", "message": "is already taken", "code": "UNIQUE_VIOLATION" }
    ],
    "request_id": "req_abc123"
  }
}
```

### Step 4: Pagination

Implement cursor-based pagination for performance, offset-based for simplicity:

#### Cursor-Based (recommended for large datasets)
```
GET /api/v1/resources?cursor=eyJpZCI6MTAwfQ&limit=20

Response:
{
  "data": [...],
  "meta": {
    "has_next": true,
    "next_cursor": "eyJpZCI6MTIwfQ",
    "limit": 20
  }
}
```

#### Offset-Based (simpler, acceptable for small datasets)
```
GET /api/v1/resources?page=2&per_page=20

Response:
{
  "data": [...],
  "meta": {
    "page": 2,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### Step 5: Rate Limiting

Add rate limiting middleware to protect endpoints:

| Endpoint Type | Rate Limit | Window |
|--------------|------------|--------|
| Authentication (login, signup) | 5 requests | 15 minutes |
| Password reset | 3 requests | 1 hour |
| API general | 100 requests | 1 minute |
| API search/list | 30 requests | 1 minute |
| Webhooks | 1000 requests | 1 minute |

Response headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1679616000
Retry-After: 30  (only on 429)
```

**Account lockout (authentication endpoints):**
- Lock account after 5 consecutive failed login attempts
- Use exponential backoff on retries (1s, 2s, 4s, 8s...)
- Consider CAPTCHA after 3 failures
- Rate limit by IP AND by account identifier (prevent distributed brute force)
- Lockout duration: 15 minutes (auto-unlock) or require email verification

429 response body:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Try again in 30 seconds.",
    "retry_after": 30
  }
}
```

### Step 6: Request Validation

Validate all input at the boundary:

- **Type checking**: Ensure fields match expected types
- **Required fields**: Reject requests missing required fields with 422
- **String limits**: Max length on all string fields (prevent payload bombs)
- **Enum validation**: Reject invalid enum values
- **Nested objects**: Validate recursively
- **Arrays**: Validate max length and element types
- **Sanitization**: Strip HTML from user input (XSS prevention)

Use framework-native validation:
- **Node.js**: Zod, Joi, or class-validator
- **Rails**: Strong Parameters + ActiveModel validations
- **Django**: Serializers with field validators
- **Go**: go-playground/validator struct tags

### Step 7: Security Middleware

Configure security headers and CORS before any endpoint code:

**Security Headers** (mandatory):
- **Node.js**: Use `helmet` middleware
- **Rails**: Use `secure_headers` gem
- **Django**: Use `django-csp` + built-in `SecurityMiddleware`
- **Go**: Custom middleware or `secure` package

Required headers:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
Referrer-Policy: strict-origin-when-cross-origin
X-XSS-Protection: 0  (rely on CSP instead)
```

**CORS Configuration** (mandatory for APIs consumed by browsers):
- Configure with an explicit allowlist of permitted origins — never use `*` for APIs that handle authentication
- Set `credentials: true` only when the client sends cookies
- Restrict `Access-Control-Allow-Methods` to the methods each endpoint actually supports
- Set `Access-Control-Max-Age` to cache preflight responses (3600s)

**SSRF Prevention** (for endpoints accepting user-provided URLs):
- Validate URL scheme (allow only `https://`)
- Block requests to private/internal IPs: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.169.254` (cloud metadata)
- Use an allowlist of permitted domains where possible
- Set timeouts on outbound requests (prevent SSRF-based DoS)

### Step 8: API Versioning

Default to URL-based versioning (`/api/v1/...`):

```
/api/v1/users    → Current stable API
/api/v2/users    → Next version (breaking changes)
```

Version in URL is explicit, discoverable, and cacheable. Header-based versioning (`Accept: application/vnd.api+json; version=2`) is an option but harder to test and debug.

### Step 9: Generate OpenAPI Spec

After endpoints are built, generate or update the OpenAPI 3.x spec:

```yaml
openapi: 3.0.3
info:
  title: [Project] API
  version: 1.0.0
paths:
  /api/v1/resources:
    get:
      summary: List resources
      parameters:
        - name: page
          in: query
          schema: { type: integer, default: 1 }
      responses:
        '200':
          description: Paginated list
```

Use framework tooling where available:
- **Node.js**: swagger-jsdoc, @nestjs/swagger
- **Rails**: rswag
- **Django**: drf-spectacular
- **Go**: swaggo/swag

## Phase Output

```
Verdict: API_SCAFFOLDED
Next: Implement business logic in service layer, then /build-implementation for TDD
Artifacts: [route definitions, controllers, validation schemas, error handlers, OpenAPI spec, rate limit config]
```
