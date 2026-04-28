# Engineering Protocol

Consolidates: engineering standards, testing standards, security baseline, ATDD protocol.

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

## Acceptance-Test-Driven Development (ATDD) Protocol

> **IRON LAW: NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) A FAILING-THEN-PASSING TEST FOR THAT AC IN THE DIFF AND (b) MUTATION SCORE >= 70% ON CHANGED LINES.**
> **IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

### Procedure (Exact, Auditable)

This is a step-by-step protocol, not a philosophy. Follow it literally. Three test invocations per slice — one batched RED, one post-implementation GREEN, one post-refactor GREEN. The mutation gate runs once at the end of the slice.

### Cycle (per slice, NOT per behavior)

1. **READ AC TEST STUBS**: Open `pipeline-state/{task-id}-plan.md` and pull the "Failing Test Stubs (per AC)" list the architect produced. Each stub names a test file, a test name, and an assertion intent. If any AC has no stub, halt and surface to the architect — implementation cannot begin.
2. **BATCHED RED**: Write every AC test as one batch (the architect's stubs are the contract). Run the suite ONCE. Capture the RED output (this is the audit artifact). Verify every batched test fails for the RIGHT reason — not syntax errors, not missing imports — the named behavior is absent.
3. **IMPLEMENT FREELY**: Write production code until every batched test passes. Run the suite ONCE. Capture the GREEN output. Shape constraints (8-line bodies, 50-line files, CC <= 5, nesting <= 2) apply continuously — fix as you go, not at the end.
4. **REFACTOR WHILE GREEN**: Tighten names, extract duplication (DRY on 2nd occurrence), confirm shape constraints on every touched file. Run the suite ONCE more. Capture the post-refactor GREEN output.
5. **MUTATION GATE**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% kill rate is required. If <70%, the slice is NOT complete — go back to step 3 with targeted tests against the surviving mutations until >= 70%.

The audit trail for the slice is exactly four artifacts: the batched RED output, the post-implementation GREEN output, the post-refactor GREEN output, and the mutation report. Code-reviewer validates all four exist and that the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

### When per-behaviour TDD Still Applies (Exceptions)

The batched-RED default does NOT apply to these cases. They keep per-behaviour RED-GREEN-REFACTOR with one test per cycle:

- **Bug fixes (always)** — the repro test IS the contract. One bug, one repro test, written and seen failing BEFORE any fix code. See `skills/bug-fix/SKILL.md`.
- **Complex algorithmic logic** — parsers, state machines, financial calculations, anything where edge cases dominate the design. The cost of finding one wrong case during batched implementation outweighs the savings of batching.
- **Security-sensitive code** — auth, crypto, ACL checks. Each rule belongs to its own RED step so the failure mode is unambiguous.

For these exceptions, the cycle is the prior per-behaviour RED -> GREEN -> REFACTOR (one test, one minimum implementation, one shape pass), repeated.

### Ordering

- The architect's plan IS the implementation order: per-AC stubs are listed in dependency order. Build foundational ACs first, composed ACs last.
- Within a slice, the entire batch is RED at once, the entire batch goes GREEN at once. There is no partial-batch RED.

### ATDD Anti-Patterns (Hard Blocks)

These are NOT allowed. If you catch yourself doing any of these, STOP and correct:

- **Partial RED**: Running the suite mid-batch with only some AC tests written. The contract is the WHOLE batch — write all stubs, run once, capture RED once.
- **Skipping the mutation gate**: A green suite is not the deliverable. The mutation report is. <70% means the tests are not exercising the changed lines, regardless of what the suite says.
- **Implementing-before-RED**: Writing a single line of source before the batched-RED output is captured. The RED output is the audit artifact that proves the behaviors were absent.
- **Deferred refactoring**: Saying "I'll clean this up later." Shape constraints apply continuously, and the post-refactor GREEN is mandatory.
- **Gold plating**: Writing source that no batched test exercises. If the test isn't in the architect's stub list, it isn't load-bearing.
- **Skipping AC-stub gate**: Starting implementation when one or more ACs has no stub. Architect must produce the stub list before BUILD begins.

### Audit Trail (per slice)

The slice produces exactly four captured outputs plus the diff:

- **Batched RED output**: every AC test red, for the right reason
- **Post-implementation GREEN output**: every test green
- **Post-refactor GREEN output**: every test still green after shape pass
- **Mutation report**: kill rate >= 70% on changed lines, with surviving-mutation list (or "0 survivors")

The code-reviewer validates all four artifacts exist and the diff contains both new tests and matching new source. Missing artifact = CHANGES_REQUESTED.

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
