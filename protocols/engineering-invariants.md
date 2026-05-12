# Engineering Invariants

Always-loaded engineering baseline: code shape, naming, error handling, dependency resolution, testing standards, security baseline. The full ATDD cycle and per-behaviour TDD exceptions live in `rules/atdd-procedure.md` and are loaded by `/build-implementation` only.

## Code Shape

Code shape is judged by **cohesion**, not by line count. AI agents can hold and reason about much larger units than humans can; mechanical line caps fragmented logic across many call sites with weak names and hurt review-time comprehension.

Hard rules (every code-touching agent enforces continuously):

- **One thing per function.** If you can describe a function as "X *and* Y", split it. The name is the test — if you cannot name it without a conjunction, it does not have a single responsibility.
- **Cyclomatic complexity ≤ 5.** Branching past this point obscures intent regardless of length.
- **Nesting ≤ 2.** Use guard clauses, polymorphism, or extraction instead of nesting deeper.
- **DRY on 2nd occurrence.** Extract immediately when logic recurs — duplication propagates bugs in any codebase.
- **Single public entry point per class** (`.call`/`.run`/`.execute`). Internal helpers stay private.

Soft warnings (advisory, surface in review but do not block):

- Function bodies past **30 lines** — usually a smell, sometimes legitimate (e.g., a large switch with no extractable cohesion).
- Files past **150 lines** — usually a smell, sometimes legitimate (e.g., a self-contained module with no fan-out).

The hook layer enforces a generous cap to catch genuinely runaway files (`CLAUDE_FILE_LINE_LIMIT`, default 300) — this is a safety net for clearly-broken output, not the design rule. The design rule is cohesion. Project overrides via `.claude/shape-overrides.json` still apply.

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

### Test Mix (behavior-driven, not ratio-driven)

The 70/20/10 pyramid was a human-cost heuristic — unit tests cheap to author, E2E expensive to author and maintain. AI authoring cost is roughly equal across tiers; the binding constraint is *runtime cost*, not authoring cost. Test mix is therefore determined by the shape of the behavior, not by a fixed ratio.

For each behavior on the changed lines, write the assertion at the **cheapest tier that can falsify it**:

- **Unit** — pure logic, isolated transformations, single-module behavior. Mocked deps. Milliseconds. Use when the behavior does not cross a module port.
- **Integration** — anything crossing a module port, a real DB, or a service boundary. Real collaborators on critical paths; mocks only at the system edge.
- **E2E** — full user journey, triggered by `protocols/e2e-protocol.md` (URL / auth / nav / WebView / cross-domain changes). Maestro for mobile, Playwright/Cypress for web.

The full proof-of-correctness tier stack (Tier 0 contracts, Tier 1 unit, Tier 1.5 property-based, Tier 2 integration, Tier 3 mutation, Tier 4 E2E) is below — the *mix* is per-behavior, but the *gates* are absolute.

The mutation gate (≥70% kill rate on changed lines) is the actual oracle for "are the tests strong enough" — not a tier ratio.

### Gates
- 80% coverage on critical paths
- No `xit`, `pending`, or `skip` -- delete untestable specs

### Zero Noise
- Every output line is a test result or a real error
- No warnings, deprecations, leaked test data, or pending specs
- Redirect test IO to StringIO, not real stderr/stdout

### Proof of Correctness (Beyond Tests)

Tests passing is necessary but not sufficient. For every feature, six tiers stack from in-source contracts up through full E2E:

- **Tier 0 — Contracts** (in-source, run as `contract.spec.*`): schema validators, type guards, runtime invariant checks at module ports. Required for changes touching public function signatures, JSON schemas, OpenAPI paths, DB schemas, or invariants. Authored at the start of the ATDD cycle (`skills/build-implementation/SKILL.md` § Write Contract Assertions) and seen RED before any production code is written. Source: GS-TDD lift / Spec-as-Contract — A7.
- **Tier 1 — Unit**: isolated, mocked deps, milliseconds.
- **Tier 1.5 — Property-Based Tests** (Hypothesis / fast-check / PropEr / equivalent): for every public function on changed lines with typed signatures, ≥1 property covering idempotence / inverse / oracle / metamorphic relations, OR a documented justification why a property is impossible. Time-boxed at 60s per function. Frozen counterexamples promote into Tier 1 as deterministic regression tests. Procedure: `skills/qa-test-strategy/SKILL.md` § Property-Based Coverage. Source: A2.
- **Tier 2 — Integration**: real boundaries, real DB, contract tests against LIVE collaborators (no mocks for critical paths), smoke tests that exercise the feature end-to-end.
- **Tier 3 — Mutation**: targeted mutation testing on changed files (Stryker / Mutant / mutmut). HARD GATE at ≥70% kill rate per `protocols/atdd-procedure.md`.
- **Tier 4 — E2E**: full user-journey tests (Maestro for mobile, Playwright/Cypress for web) for URL / auth / nav / WebView / cross-domain changes (conditional per `rules/e2e-protocol.md` trigger matrix).

Feature is VERIFIED when applicable tiers pass. Tiers 0-3 are always required. Tier 4 is conditional. Tier 0 is required only for changes touching public function signatures, schemas, or invariants — pure UI copy or log-format tweaks may skip with documented rationale. Tier 1.5 is required for changes touching public functions with typed signatures (same gate as the qa-engineer checklist).

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
