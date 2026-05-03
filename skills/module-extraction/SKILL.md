---
name: "module-extraction"
description: "Use when user wants to extract a bounded context into an in-process module with an explicit public port (same repo, no new process or deploy unit). Default answer to 'extract/split/separate X' when no forcing function is named."
context: fork
agent: software-engineer
argument-hint: "What to extract into a module (e.g., 'extract billing into a module with an explicit port')"
---

# Module Extraction

## What This Skill Does

Carves a bounded context out of the host codebase **within the same repo**. Produces a new package/namespace with an explicit port (interface), keeping everything in-process: no new repo, no new runtime, no network hop, no new deploy unit. This is the default answer to "extract/split/separate X" when no forcing function is named.

Phases 1–2 ship executable in the MVP and produce reviewable artifacts (a boundary-analysis document and a contract file). Phases 3–6 ship as outline — the standard Build phase drives them via TDD against the Phase 2 contract until a follow-up pipeline codifies them into executable skill phases.

## When to Invoke

- A module has grown and is hard to change in isolation; it is tangled with neighbors
- The user said "extract X", "split Y out", "separate Z", or "move W into its own thing" **with no forcing function named**
- An existing bounded context needs an explicit port so neighbors stop reaching into its internals

## Out of Scope

- Anything requiring a new process, repo, runtime, or network hop
- Any request that names a forcing function from `rules/_detail/module-boundaries-protocol.md`

If a forcing function is detected in the task context or pipeline state, the skill exits immediately with `WRONG_SKILL: route to /service-extraction`. The orchestrator auto-reroutes per the `WRONG_SKILL` handler contract.

## Phases

| Phase | Executable? | Inputs | Outputs | Verdict on failure |
|-------|-------------|--------|---------|--------------------|
| 1. Boundary analysis | **EXECUTABLE (MVP)** | Target module name, current file tree | Written artifact: files belonging to module, inbound deps, outbound deps, shared-state audit | `EXTRACTION_BLOCKED: shared-state must be resolved first` |
| 2. Contract design | **EXECUTABLE (MVP)** | Phase 1 artifact | Reviewable `interface.{ext}` in target module directory (optional split: `types.{ext}`, `events.{ext}`) | `EXTRACTION_BLOCKED: no clean port — module is not cohesive enough to extract` |
| 3. Directory move + namespace | OUTLINE (follow-up) | Contract, file list | Files moved to `src/modules/{name}/` (or language equivalent); internal imports updated; external callers transitioned via shim/barrel export | `EXTRACTION_BLOCKED: circular dependency surfaced` |
| 4. Enforce the seam | OUTLINE (follow-up) | New module location | Every external caller imports only from the public entry point; lint rule or import boundary check added (see per-language table) | `EXTRACTION_BLOCKED: caller cannot be refactored to use the port` |
| 5. Seam test | OUTLINE (follow-up) | Module + lint rule | One test that exercises the module only through its port, with collaborators mocked/injected | `EXTRACTION_BLOCKED: seam is not testable` |
| 6. DI wiring | OUTLINE (follow-up) | Module | Any SDK/IO the module needs is injected via constructor or module initialization — not reached for globally | `EXTRACTION_BLOCKED: hidden dependency` |

## Phase 1 — Boundary Analysis (Executable)

Produces a written artifact that downstream phases and the Build pipeline consume.

### Procedure

1. **Name the target module**: extract the target from the argument (e.g., `billing`). Record the canonical name.
2. **Enumerate files belonging to the module**:
   - Start with the obvious directory (`src/billing/`, `app/services/billing/`, `lib/billing/`).
   - Grep for class/module names owned by the domain (e.g., `Billing`, `Invoice`, `Subscription`).
   - Include tests that exclusively exercise those files.
3. **Inbound dependencies** (who calls INTO the module):
   - Grep the rest of the codebase for imports of any file in the module's file list.
   - For each hit, record: `{caller file} → {module symbol}`.
4. **Outbound dependencies** (what the module calls OUT to):
   - For each module file, list imports that are NOT within the module's file list.
   - Classify each as: `internal-host` (other host code — becomes a seam concern), `shared-library` (fine to keep), `third-party SDK` (DI candidate for Phase 6).
5. **Shared-state audit**:
   - Grep within the module for module-level mutable state (globals, singletons, `let` at module scope, class variables, `$`-globals).
   - Grep for writes to state owned by OTHER modules (cross-boundary mutation — breaks extraction).
   - If either is present and cannot be resolved → return `EXTRACTION_BLOCKED: shared-state must be resolved first` with the specific state cited.
6. **Write the artifact** to `pipeline-state/{task-id}/boundary-analysis.md`.

### Artifact Format

```markdown
---
task_id: {task-id}
phase: boundary-analysis
module: {module-name}
timestamp: {ISO 8601}
---

## Module
- Name: {module-name}
- Target location (proposed): src/modules/{module-name}/ (or language equivalent)

## Files Belonging to Module
- {path 1}
- {path 2}
- ...

## Inbound Dependencies (callers → module symbols)
| Caller | Symbol Used | Notes |
|--------|-------------|-------|
| {file} | {Class.method or function} | {transient? foundational? refactor risk?} |

## Outbound Dependencies (module → other code)
| Target | Kind | DI Candidate? |
|--------|------|---------------|
| {import} | internal-host / shared-library / third-party SDK | yes / no |

## Shared-State Audit
- Module-level mutable state inside module: {list or "none"}
- Writes to state owned by other modules: {list or "none"}
- Resolution plan (if state found): {move to instance state / inject / block extraction}

## Verdict
BOUNDARY_ANALYZED | EXTRACTION_BLOCKED: {reason}
```

### Inputs consumed from: task argument, current file tree.
### Output consumed by: Phase 2 (contract design).

## Phase 2 — Contract Design (Executable)

Produces the module's public port as a reviewable source file.

### Procedure

1. **Read the Phase 1 artifact** from `pipeline-state/{task-id}/boundary-analysis.md`.
2. **Derive the public surface** from the Inbound Dependencies table:
   - Every inbound symbol is a candidate for the port.
   - Collapse near-duplicates (e.g., two callers calling `getSubscription` with different param shapes → one signature with a union or overload).
3. **Draft the port**: write signatures (not implementations) for every public entry point. Include parameter types, return types, error types, and a one-line doc comment stating the invariant.
4. **Co-locate with the module**: write the contract file into the module's directory — `{module-path}/interface.{ext}` (where `{ext}` matches the host language: `ts`, `rb`, `py`, `go`).
5. **Split when warranted**: if the interface file exceeds what a reader can hold in their head, split into `interface.{ext}` + `types.{ext}`; add `events.{ext}` when the module emits domain events.
6. **Validate cohesion**: if the port has unrelated clusters of operations (e.g., `createInvoice` sitting next to `recordClickstream`), the module is not cohesive enough to extract → return `EXTRACTION_BLOCKED: no clean port`.

### Output Format

A source file in the module directory. Example (TypeScript):

```typescript
// src/modules/billing/interface.ts
// Public port for the billing module.
// Invariant: all billing operations scope to a single userId.

export interface BillingPort {
  /** Returns active subscription or null. */
  getSubscription(userId: UserId): Promise<Subscription | null>;
  /** Charges the user; throws PaymentDeclined on failure. */
  charge(userId: UserId, amount: Money): Promise<ChargeResult>;
  /** Cancels subscription; idempotent. */
  cancel(userId: UserId): Promise<void>;
}
```

Shape guidance: the port is a pure signature surface — no implementation, no default methods with logic, no private helpers. Implementations live in the module's internal files (invisible to callers by Phase 4).

### Inputs consumed from: Phase 1 artifact.
### Output consumed by: Phases 3–6 (Build pipeline implements against this contract).

## Phases 3–6 — Outline (Future Work)

Full procedural implementation is deferred to a follow-up pipeline. Until that pipeline ships, the standard Build phase drives these against the Phase 2 contract via `/build-implementation` using TDD.

- **Phase 3 — Directory move + namespace**: move module files into `src/modules/{name}/` (or language equivalent: `app/modules/` for Rails, `internal/` for Go, `{package}/modules/` for Python). Update internal imports. Preserve external callers via shim/barrel export during transition.
- **Phase 4 — Enforce the seam**: add a lint rule or compiler boundary check so external code can only import from the port (see per-language table below). Remove the transitional shim after all callers migrate.
- **Phase 5 — Seam test**: one test that exercises the module solely through the port with all collaborators injected. Proves the contract is honored without white-box access.
- **Phase 6 — DI wiring**: convert module-internal reach-outs (SDKs, DB clients, HTTP clients) into constructor-injected dependencies. No global lookups from within the module.

## Per-Language Lint Rule Table

Seam enforcement for Phase 4. This table lives here; `rules/_detail/module-boundaries-protocol.md` carries only the pointer.

| Language | Tool | Mechanism |
|----------|------|-----------|
| TypeScript/JavaScript | ESLint `no-restricted-imports` | Disallow deep-import patterns into module internals; allow only the public entry point |
| Ruby | `packwerk` | Pack boundary + public API declaration; `packwerk validate` in CI |
| Python | `import-linter` | Contracts declaring module layers and forbidden imports |
| Go | Internal packages | `internal/` directory enforces compiler-level visibility |

## Verdicts

- **`MODULE_EXTRACTED`** — all six phases green: boundary analyzed, contract designed, directory moved, seam enforced by lint rule, seam test passing, dependencies injected. Full-implementation path; reachable only after the follow-up pipeline ships phases 3–6 as executable.
- **`BOUNDARY_READY`** — phases 1–2 complete, artifacts produced (boundary-analysis doc + contract source file). The standard Build pipeline then drives phases 3–6 via TDD against the contract. **This is the MVP verdict.**
- **`EXTRACTION_BLOCKED: {reason}`** — one of the failure conditions from the phase table. Not an escalation to `/service-extraction` — it's a signal the module isn't ready to be a module yet.
- **`WRONG_SKILL`** — a forcing function was detected mid-flow (should have been caught at intake). Hand off to `/service-extraction` with the same task context per the orchestrator's `WRONG_SKILL` handler contract.

## Contrast: /module-extraction vs /service-extraction

| Dimension | `/module-extraction` | `/service-extraction` |
|-----------|----------------------|-----------------------|
| Process boundary | Same process | New process |
| Repo | Same repo | New repo |
| Contract | In-language interface/port | OpenAPI / Protobuf / event schema |
| Calls | Function calls | HTTP / gRPC / message queue |
| Deploy | Same deploy unit | Independent deploy |
| Failure model | Exception propagation | Network failure + retry + circuit breaker |
| State | Shared in-process | Separate database |
| Tests at seam | Injected collaborators | Contract tests against live service |
| Trigger | Cohesion pressure | A forcing function (FF1–FF5) |
| Reversibility | Trivial (rename/move) | Expensive (repo + data + deploy rollback) |

## References

- `rules/_detail/module-boundaries-protocol.md` — single source of truth for what a module is, module contract artifacts, testing at the seam, the canonical forcing-function list (FF1–FF5), and the decision checklist. Do not duplicate that content here; link to it.
$ARGUMENTS
