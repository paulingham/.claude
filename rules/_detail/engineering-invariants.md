# Engineering Invariants

Always-loaded engineering baseline: code shape, naming, error handling, dependency resolution, testing standards, security baseline. The full ATDD cycle and per-behaviour TDD exceptions live in `rules/atdd-procedure.md` and are loaded by `/build-implementation` only.

## Code Shape

- Methods/functions: 8 lines max (configurable per project via `CLAUDE_FUNCTION_LINE_LIMIT`), CC <= 5, nesting <= 2
- Classes/files: 50 lines max (configurable per project via `CLAUDE_FILE_LINE_LIMIT`)
- Project overrides: place a `shape-overrides.json` in the project's `.claude/` directory with per-glob limits (e.g., `{"*.rb": 80, "*.go": 100}`)
- Classes: single public entry point (`.call`/`.run`/`.execute`)
- DRY: 2nd occurrence -> extract immediately

## When to Use a Class vs Standalone Function

**Use a class (service object) when ANY of these are true:**
- Module-level mutable state exists (`let counter = 0`) -> that state MUST be instance state
- 3+ functions share a common external dependency (SDK, API client, storage) -> inject via constructor
- Functions are always used together and never independently -> they are one cohesive unit
- An if/else chain dispatches on type -> use strategy pattern with polymorphism
- Test setup requires `jest.mock()` on an SDK -> inject the dependency instead

**Use standalone functions when ALL of these are true:**
- Pure function (no side effects, no shared state)
- No external dependencies to inject (or dependency is stable platform API like `URL`)
- Function is independently useful (not part of a tightly coupled group)

**React exception:** Hooks and components stay as functions -- React's model handles state via `useState`/`useRef`. But `lib/` layer business logic follows the class rules above.

## Naming

- Intention-revealing, no abbreviations, describe what not how
- Booleans read as questions (`valid?`, `enabled?`, `is_active`)
- If a name needs a comment, rename it

## SOLID (one-liner reminders)

- SRP: one reason to change -- OCP: extend, don't modify -- LSP: honor contracts
- ISP: small interfaces -- DIP: inject dependencies via constructor
- DIP applies to `lib/` layer: if a function calls an SDK, that SDK must be injectable

## Error Handling

- Never fail silently -- surface with context (correlation ID, input params, stack)
- Retry transient failures with exponential backoff
- Guard clauses on public methods

## Dependency Resolution

When importing a new package:
1. Verify the compiler/type-checker resolves it (`tsc`, `mypy`, `rubocop`, etc.)
2. Verify the test runner resolves it (may need a mock or explicit install)
3. If the module is transitively available (bundled inside a parent package),
   install it explicitly as a direct dependency — transitive resolution is fragile
4. If the test runner can't load the real module (native dependencies, font loading, etc.),
   add a project-level mock (`__mocks__/`, `conftest.py`, `spec/support/`, etc.)

## Self-Sufficiency

- Validate your own work before marking done
- Run linting and tests before declaring complete

## Testing Standards

> The full ATDD cycle (batched RED, mutation gate, anti-patterns, audit trail) is in `rules/atdd-procedure.md`. The standards below are universal and always apply.

### Pyramid
- **70% Unit** -- isolated, mocked deps, milliseconds
- **20% Integration** -- real DB, service boundaries, seconds
- **10% E2E** -- critical user workflows only; Maestro for mobile (see `rules/e2e-protocol.md`)

### Gates
- 80% coverage on critical paths
- No `xit`, `pending`, or `skip` -- delete untestable specs

### Zero Noise
- Every output line is a test result or a real error
- No warnings, deprecations, leaked test data, or pending specs
- Redirect test IO to StringIO, not real stderr/stdout

### Proof of Correctness (Beyond Tests)

Tests passing is necessary but not sufficient. For every feature:
- **Tier 1**: Contract tests against real boundaries (not mocks for critical paths)
- **Tier 2**: Smoke tests that exercise the actual feature end-to-end
- **Tier 3**: Targeted mutation testing on changed files (verify tests catch real bugs)
- **Tier 4**: E2E tests via Maestro for URL/auth/nav/WebView changes (conditional per `rules/e2e-protocol.md`)

Feature is VERIFIED when applicable tiers pass. Tiers 1-3 are always required. Tier 4 is conditional -- see `rules/e2e-protocol.md` for trigger criteria.

### Known Deprecations (append-only)
- `:unprocessable_entity` -> `:unprocessable_content` (Rack 3.x, HTTP 422)

## Security Baseline

### Input & Data
- Parameterized queries only -- no SQL interpolation
- Input validation on all external boundaries
- Content-Type validation on file uploads

### Secrets & Access
- No secrets in code, commits, or logs
- RBAC deny-by-default at controller/resolver level
- HTTPS everywhere, secure cookie flags (HttpOnly, Secure, SameSite)

### Dependencies
- Audit dependencies before shipping (`bundle audit`, `npm audit`, `pip-audit`)
- Lock files committed, no outdated packages with known CVEs

### Environment Segregation
- Local/staging/production environments fully isolated
- Environment-specific secrets never shared across boundaries
- CI/CD pipelines verify no prod credentials in test
