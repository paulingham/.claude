# Engineering Invariants

Always-loaded engineering baseline: code shape, naming, error handling, dependency resolution, testing standards, security baseline. The full ATDD cycle and per-behaviour TDD exceptions live in `protocols/atdd-procedure.md` and are loaded by `/harness:build-implementation` only.

## Code Shape

The goal: small single-responsibility units composed together — tiny by default (Ruby small-object tradition).

**Naming is the primary cohesion gate** — it cuts both ways:
- Cannot name a unit without "and" → it is too big, split it.
- Cannot give an extracted piece an honest name → do NOT extract. A fragment named `handlePart2` is worse than the longer cohesive function.

**Per-language length limits — HARD BLOCK on new/changed code; advisory on legacy:**
- Ruby methods: **> 5 lines** blocked (exit 2) by hook on new/changed code; advisory on pre-existing.
- TypeScript/JavaScript functions: **> 12 lines** blocked on new/changed code; advisory on pre-existing.
- Python/Go: existing cap (`CLAUDE_FUNCTION_LINE_LIMIT`, default 8) retained.

**Entanglement escape valve (Ousterhout):** if understanding unit A requires reading unit B (you flip between them), do NOT split — bring them together. This is guidance on HOW to fix a flagged function, not an escape hatch from the block.

**Deep modules, not many shallow ones (Ousterhout):** prefer one deep unit with a simple interface hiding substantial implementation over several shallow ones whose combined interface costs more than they hide.

Hard rules (every code-touching agent enforces continuously):

- **One thing per function.** Naming is the test — if you cannot name it without a conjunction, split.
- **Cyclomatic complexity ≤ 5.** Branching past this point obscures intent regardless of length.
- **Nesting ≤ 2.** Use guard clauses, polymorphism, or extraction instead of nesting deeper.
- **DRY on 2nd occurrence.** Extract immediately when logic recurs — duplication propagates bugs in any codebase.
- **≤ 4 params** per function. More signals a missing abstraction or a god-function.
- **Single public entry point per class** (`.call`/`.run`/`.execute`). Internal helpers stay private.

**Classes/files:** one responsibility per class/module — size is a smell that triggers the naming check, not a hard rule. There is no 100-line class cap (folklore; refuted). The hook enforces a generous safety-net cap (`CLAUDE_FILE_LINE_LIMIT`, default 300) for genuinely runaway files only. Project overrides via `.claude/shape-overrides.json` still apply.

## Simplicity

Simple means **don't complect** (Hickey): one concern per unit, not braided or interleaved with others. The check is concrete — does this unit interleave concerns that could stand alone?

Simplicity is a prerequisite for reliability (Dijkstra/Hickey): you can only make reliable what you can reason about; complected code defeats reasoning combinatorially.

## Connascence

Two units are connascent if a change in one forces a change in the other to stay correct — this is the WHY under DRY, SOLID, ≤4 params, and single entry point.
**Strength spectrum (weak→strong; dynamic > static):**
- Static: Name → Type → Meaning/Convention → Position → Algorithm
- Dynamic: Execution → Timing → Value → Identity

**Two axes:** **degree** (how many components share the connascence) and **locality** (how close they are).

**Rule:** the stronger the connascence, the more local it must be. Minimise strength AND degree across module boundaries; convert strong-remote connascence to weak-local.

**Example:** `place_order(user_id, org_id)` — two raw strings in fixed slots = Connascence of Position (strong).
- Named-params object `{ userId, orgId }` → Connascence of **Name** (kills slot-order coupling; both fields still `string`, so a `{ userId: orgId }` swap still compiles).
- Distinct value objects `UserId` / `OrgId` → Connascence of **Type** (kills the same-type swap; compiler-enforced).

## Comments

**Code carries the WHAT. Comments carry only the WHY** — intent, rationale, non-obvious constraints, public-API contracts, and warnings of consequences.

**Banned (a new explanatory WHAT comment in changed source is blocked by hook):**
- Restating what the code does (`# Increment counter` next to `counter += 1`)
- Changelog/apology comments (`# Changed because reviewer said X`)
- Commented-out code

**Always allowed:** public-API doc-comments (`/** */`, `# @param`, `"""…"""`), legal/license headers, and WHY-prefix notes (`# WHY:`, `# SAFETY:`, `# NOTE:`) for genuinely non-obvious constraints.

- Banned: `# Iterate over users and send email` (restates the loop below it).
- Allowed: `# WHY: Stripe requires idempotency key on retries — removing this causes duplicate charges.`

If a name needs a comment, rename it. If a *constraint* is not obvious from the code, comment the WHY.

The comment-smell hook blocks only high-confidence narration (bare lowercase-verb prose that restates adjacent code); intent, contract, warning, and rationale comments — ideally prefixed `WHY:`/`WARNING:`/`CONTRACT:`/`FIXME:` etc. — always pass.

### DEBT: markers — deliberate-simplification debt

A `DEBT:` comment records an accepted simplification and the condition that should prompt revisiting it. The grammar is `DEBT: <ceiling>, <upgrade-trigger>`:

- **ceiling** — the accepted complexity / simplification limit (what we deliberately did NOT build).
- **upgrade-trigger** — the condition that should prompt revisiting it (the second clause, after the comma).

```ruby
# DEBT: inline cache keyed by prefix, upgrade to an LRU when prefixes > 3
```

An entry with **no upgrade-trigger** (no second clause after the comma) is silent rot — debt with no exit condition that accumulates invisibly. `DEBT:` is colon-strict (a bare `# DEBT` without the colon is not specially exempted) and is harvested by `/harness:debt-ledger`, an advisory collector that renders the open ledger and flags every `no-trigger` entry.

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

## Type Discipline

**No primitive obsession at module ports** — a raw `string`, `UUID`, `number`, or `bool` carrying domain meaning across a module boundary should be a domain type or Value Object (`Email`, `Money`, `UserId`), not a primitive. Scoped to ports/boundaries only: raw primitives are fine for local scratch variables (e.g. a loop counter). Judgment-feeding (reviewer/architect).
- Before: `sendInvoice(customerId: string, amount: number)` at a module port. After: `sendInvoice(id: CustomerId, amount: Money)` — the compiler enforces the agreement.

**Immutability by default** — prefer immutable data; mutation is a justified exception that MUST carry a `# WHY:` comment (reuses the WHY-prefix convention from `## Comments`). Judgment-feeding.
- Justified: `# WHY: in-place accumulation; copy-per-iter is O(n²) on 50k rows`

**Acyclic dependencies** — the module/import dependency graph must be acyclic; dependencies point inward toward stability (extends the DIP rule in `## SOLID`). Judgment-feeding (import-cycle enforcement hook not yet wired; treat as design guidance).

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

> The full ATDD cycle (batched RED, mutation gate, anti-patterns, audit trail) is in `protocols/atdd-procedure.md`. The standards below are universal and always apply.

### Test Mix (behavior-driven, not ratio-driven)

The 70/20/10 pyramid was a human-cost heuristic — unit tests cheap to author, E2E expensive to author and maintain. AI authoring cost is roughly equal across tiers; the binding constraint is *runtime cost*, not authoring cost. Test mix is therefore determined by the shape of the behavior, not by a fixed ratio.

For each behavior on the changed lines, write the assertion at the **cheapest tier that can falsify it**:

- **Unit** — pure logic, isolated transformations, single-module behavior. Mocked deps. Milliseconds. Use when the behavior does not cross a module port.
- **Integration** — anything crossing a module port, a real DB, or a service boundary. Real collaborators on critical paths; mocks only at the system edge.
- **E2E** — full user journey, triggered by `protocols/e2e-protocol.md` (URL / auth / nav / WebView / cross-domain changes). Maestro for mobile, Playwright/Cypress for web.

The full proof-of-correctness tier stack (Tier 0 contracts, Tier 1 unit, Tier 1.5 property-based, Tier 2 integration, Tier 3 mutation, Tier 4 E2E) is below — the *mix* is per-behavior, but the *gates* are absolute.

The mutation gate (≥70% kill rate on changed lines) is the actual oracle for "are the tests strong enough" — not a tier ratio. The active, time-boxed path to reach this threshold is the Mutation Kill Loop defined in `protocols/atdd-procedure.md` step 4.

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
- **Tier 3 — Mutation**: targeted mutation testing on changed files (Stryker / Mutant / mutmut). HARD GATE at ≥70% kill rate, reached via the active per-slice atdd-procedure.md step 4 Mutation Kill Loop (see `protocols/atdd-procedure.md`).
- **Tier 4 — E2E**: full user-journey tests (Maestro for mobile, Playwright/Cypress for web) for URL / auth / nav / WebView / cross-domain changes (conditional per `protocols/e2e-protocol.md` trigger matrix).

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
