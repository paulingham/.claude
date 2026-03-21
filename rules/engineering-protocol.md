# Engineering Protocol

Consolidates: engineering standards, testing standards, security baseline, incremental TDD protocol.

## Code Shape

- Methods/functions: 5 lines max, CC <= 5, nesting <= 2
- Classes/files: 50 lines max
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

## Incremental TDD Protocol

### Procedure (Exact, Auditable)

This is a step-by-step protocol, not a philosophy. Follow it literally.

### Cycle (repeat for each behavior)

1. **RED**: Write ONE failing test. Run it. Verify it fails for the RIGHT reason (not a syntax error, not a missing import -- the actual behavior is absent).
2. **GREEN**: Write the MINIMUM code to make that one test pass. Run ALL tests. Verify ALL green.
3. **REFACTOR**: Check shape constraints on every touched file:
   - Every function body <= 5 lines? If not, extract now.
   - File <= 50 lines? If not, decompose now.
   - CC <= 5? Nesting <= 2? Fix now.
   - Run ALL tests again. Confirm GREEN.
4. **REPEAT** from step 1 with the next behavior.

### Ordering

- Decompose acceptance criteria into an ordered list of test cases BEFORE writing any code.
- Implement in dependency order: foundational behaviors first, composed behaviors last.
- Each cycle produces one test and the minimum code to pass it.

### TDD Anti-Patterns (Hard Blocks)

These are NOT allowed. If you catch yourself doing any of these, STOP and correct:

- **Bulk testing**: Writing 2+ tests before any implementation code.
- **Skipping RED**: Writing a test that already passes. If it passes immediately, the test is not testing new behavior -- delete it or fix it.
- **Deferred refactoring**: Saying "I'll clean this up later." Refactor happens in EVERY cycle, not at the end.
- **Test-then-implement**: Writing all tests in one block, then all implementation in another block.
- **Gold plating**: Writing more code than the current failing test requires.

### Audit Trail

Each RED -> GREEN -> REFACTOR cycle MUST produce visible output:
- The failing test output (RED)
- The passing test output (GREEN)
- Any refactoring changes with test confirmation (REFACTOR)

The code-reviewer validates this trail exists. Missing trail = CHANGES_REQUESTED.

## Testing Standards

### TDD: Red-Green-Refactor (MANDATORY)
1. **RED**: Failing test first. Verify it fails for the right reason.
2. **GREEN**: Minimum code to pass.
3. **REFACTOR**: Clean up while green.

Never skip RED -- if you didn't see it fail, you don't know the test works.

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
