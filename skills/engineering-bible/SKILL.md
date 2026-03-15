---
name: "Engineering Bible"
description: "Single source of truth for all engineering standards. Enforced on every task. Covers CC=1, 5-line methods, SOLID, DRY, testing pyramid, design patterns, security, and observability."
---

# Engineering Bible

Single source of truth for all engineering standards. Enforced on every task.

## Cyclomatic Complexity = 1

Every method has a single execution path. Replace branching with polymorphism, strategy pattern, or lookup tables. If you write `if/else` or `case/when`, extract a class.

## 5-Line Method Limit

Methods longer than 5 lines violate Single Responsibility. Extract private methods with intention-revealing names. No exceptions.

## Class Design

Classes are contracts with a single public entry point (`.call`, `.run`, `.execute`). All other methods are private. If you need two public methods, you need two classes.

## SOLID Principles

- **SRP**: One reason to change per class
- **OCP**: Open for extension, closed for modification
- **LSP**: Subtypes must honor base contracts
- **ISP**: Small, focused interfaces over fat ones
- **DIP**: Depend on abstractions, inject dependencies

## DRY (3-Strike Rule)

- First occurrence: write it
- Second occurrence: note duplication
- Third occurrence: extract shared abstraction

## Convention Over Configuration

Use framework defaults. Deviate only with documented justification. Respect the ecosystem conventions for your language and framework.

## Lean Agile Mindset

- Thin vertical slices delivering observable user value
- MVP scope: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Kill criteria: know when to stop investing

## Multi-Language Awareness

Detect language from codebase context. Respect user preference. Apply language-appropriate conventions:
- **Ruby**: Rails conventions, snake_case, RSpec
- **JavaScript/TypeScript**: Node patterns, camelCase, Jest
- **Python**: PEP 8, snake_case, pytest

## Naming Conventions

Intention-revealing names, no abbreviations:
- **Classes**: PascalCase nouns - `UserAuthenticationService`, not `Auth`
- **Methods**: snake_case verbs - `calculate_total_price`, not `calc`
- **Booleans**: `is_`, `has_`, `can_` prefix - `is_valid?`, not `valid`
- **Constants**: SCREAMING_SNAKE_CASE - `MAX_RETRY_ATTEMPTS`, not `MAX`
- **Rule**: If you need a comment to explain the name, rename it

## Testing Pyramid

| Layer | Share | Owner | Scope |
|-------|-------|-------|-------|
| Unit | **70%** | Software Engineer | Single class in isolation |
| Integration | **20%** | Software Engineer | Component boundaries, DB |
| E2E | **10%** | QA Engineer | Full user workflows |

- **Coverage**: 80% line coverage gate
- **TDD**: Red-Green-Refactor, mandatory
- **Incremental**: One test at a time. Never write the full suite upfront.
- **Isolation**: Each test independent, no shared mutable state

## Design Patterns

Use proper OO design. Encouraged patterns:
- **Decorator**: Extend behavior without modifying originals
- **Presenter**: View-specific formatting logic
- **Strategy**: Swappable algorithms
- **Observer**: Event-driven decoupling
- **Repository**: Data access abstraction
- **Value Object**: Immutable domain concepts
- **Form Object**: Complex validation logic
- **Query Object**: Reusable database queries

## Security (OWASP Top 10 Checklist)

- [ ] Parameterized queries only (no SQL interpolation)
- [ ] Escape all user-generated content (XSS)
- [ ] RBAC with deny-by-default
- [ ] No secrets in code or commits
- [ ] Strong password hashing (bcrypt/argon2)
- [ ] HTTPS everywhere, secure cookies
- [ ] Rate limit all endpoints
- [ ] CSRF protection enabled
- [ ] Dependency audit after any addition
- [ ] Security events logged (no credentials in logs)

## Error Handling Patterns

- Exception hierarchy: `ApplicationError` base -> `ValidationError`, `NotFoundError`, `AuthorizationError`
- Global exception handler: middleware mapping error classes to HTTP status codes
- Error boundaries (React): wrap route segments, provide fallback UI
- Structured error logging: `correlation_id`, error class, message, truncated backtrace
- Guard clauses on public methods
- Descriptive error messages suggesting remediation
- Retry with exponential backoff for transient failures
- Never fail silently — always surface errors to logs and callers

## Logging and Observability

- **Format**: Structured JSON: `timestamp`, `level`, `message`, `correlation_id`, `metadata`
- **Levels**: DEBUG (dev only), INFO (request lifecycle), WARN (recoverable), ERROR (needs attention)
- **Log**: Request start/end, external API calls, job lifecycle, auth events, errors
- **Never log**: Passwords, tokens, API keys, PII, credit cards, session IDs
- **Correlation IDs**: Generate at request entry, propagate through services and jobs
- **Health**: `/health` (liveness), `/ready` (readiness — dependencies connected)

## Configuration Management

- 12-factor: all config via environment variables, never hardcoded
- Naming: `APPNAME_COMPONENT_SETTING` (e.g., `MYAPP_REDIS_POOL_SIZE`)
- Secrets never in code or git — use env vars or vault. Fail fast if missing.
- Feature flags via env vars or flag service for gradual rollout

## Performance Engineering

- Use EXPLAIN on slow queries. Index columns in WHERE/ORDER/JOIN.
- Cache: HTTP Cache-Control for static assets, Redis for computed data
- Lazy loading: dynamic imports (JS), lazy associations (ORMs)
- Pagination: never load unbounded collections
- Batch operations: bulk inserts, bulk upserts — never loop-and-save

## Authentication and Authorization

- Passwords: bcrypt or argon2 only
- Sessions: secure cookies, short expiry, rotate on login
- JWT: validate signature, check expiry, verify issuer/audience. Short-lived access + refresh tokens.
- RBAC: deny-by-default at controller/resolver level, never in views
- API keys: hash before storing, rotate regularly, scope to minimum permissions
