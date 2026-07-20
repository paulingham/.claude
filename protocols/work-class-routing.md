# Work-Class Routing Protocol

How the harness decides **which dispatch shape a task gets**. The goal is to prevent a doc edit from paying feature-sized dispatch cost while preserving full pipeline rigour for real engineering work.

> **SSOT note (Phase D Wave 2):** This protocol previously described a seven-tier (T0-T6, T3H) fingerprint computed inside `/harness:intake` Step 1.5. That computation has been superseded by the **three-gear classifier** (`hooks/_lib/gear-select.sh`), which runs on `UserPromptSubmit` and persists its verdict to `gear-${sid}` session state before intake or pipeline dispatch begins. This document now describes the gear architecture. The legacy tier-based Step 1.5 fingerprint prose in `skills/intake/SKILL.md` and the Step 1.0 Tier Guard in `skills/pipeline/SKILL.md` still exist and are consumed by a live forensics hook (`hooks/_lib/intake-fingerprint-emit.py`) — their tier→gear migration is out of scope for this wave and tracked separately.

## Why this exists

A doc-only sweep and a feature share the same pipeline shape if their budget+critical happen to match, absent a class-first check. User phrasing (`critical`, `important`) is trusted directly unless cross-checked. Result: low-stakes work can route through Plan → heavy challenger team → multi-slice Build → 5-agent Final Gate, burning 12-15 subagent spawns for what amounts to a find/replace.

## Design principle

> **Task class is orthogonal to budget. Auto-detection overrides user phrasing. Every override is logged.**

Three rules govern routing:

1. **Class first, budget second.** Classify the work into one of three gears — **PAIR**, **BUILD**, **PIPELINE** — based on **what the request implies** (keyword/shape evidence in the prompt), not what the user said about stakes. Budget informs *intra-gear* shape (e.g. multi-slice Build), not *which gear*.
2. **Default light, escalate on evidence.** Polarity is inverted from the legacy tier fingerprint: the default gear is **PAIR** (the lightest), escalating to BUILD or PIPELINE only when a detector positively fires. A gate that cannot evaluate its input (empty/malformed prompt) fails to the **heaviest** gear (PIPELINE) — fail SAFE means fail HEAVY, never silently light.
3. **Bidirectional override with forensics.** Natural-language overrides ("just pair", "build it", "full pipeline") force a specific gear. Overrides are logged.

## The three gears

| Gear | Default? | Class | Examples | Dispatch target |
|---|---|---|---|---|
| **PAIR** | Yes (default) | Question / doc / config / mechanical / trivial code | "How does X work?", README edits, settings.json keys, rename sweeps, ≤1-file/≤15-line trivial code | Direct answer, or one of the PAIR sub-behaviours below |
| **BUILD** | No — escalate on evidence | Bug fix / standard feature | Failing test + targeted fix, new AC in an isolated module, "build it", "implement this feature" | One worktree subagent, TDD, code-review, PR |
| **PIPELINE** | No — escalate on evidence | Critical / cross-cutting | Auth, payment, security, multi-repo, schema/migration work, "full pipeline" | Full multi-agent `/harness:pipeline` (Plan → Plan Validation → Build → Security Review → Final Gate → Ship → Deploy → Reflect) |

### PAIR sub-behaviours (dispatch capabilities preserved from the tier model)

PAIR is not one dispatch target — it is the lightest gear, and its own classifier hands off to whichever lightweight capability fits the request shape. These capabilities are unchanged from the retired tier model; only the outer classification vocabulary changed:

| Request shape | PAIR sub-behaviour |
|---|---|
| Question / spike ("How does X work?", "Investigate Y") | Direct answer, or `/harness:tech-spike` for a throwaway prototype |
| Tracked-doc edit (README/CLAUDE.md/protocol updates, comments) | Lightweight worktree subagent (Iron Law 3 — orchestrator never writes source directly; delegates to a worktree subagent) |
| Config-only (settings.json keys, agent frontmatter, hook entry syntax — NOT hook script bodies) | `/harness:harness-config` |
| Mechanical sweep (rename, find/replace, lint-fix, import-sort, dependency bump across ≥3 uniform files) | `/harness:batch-pipeline` |

BUILD and PIPELINE are single dispatch targets — BUILD always means one worktree subagent running Build phase + code-review + Ship; PIPELINE always means the full `/harness:pipeline` phase sequence (with Best-of-N or PDR-RTV Build variants for the heaviest cases, gated by budget+critical exactly as the retired T6 tier was).

## Gear classification (`hooks/_lib/gear-select.sh`)

Runs on every `UserPromptSubmit`, before `/harness:intake` or `/harness:pipeline` dispatch. No fingerprint computation inside intake — the gear is already resolved and persisted by the time intake runs.

### Override detection (checked first)

Natural-language override phrases in the prompt force a specific gear regardless of classification evidence:

| Phrase pattern | Forced gear |
|---|---|
| "just pair" / "pair on this" | PAIR |
| "build it" / "build this properly" | BUILD |
| "ship it properly" / "take it all the way" / "full pipeline" | PIPELINE |

### Evidence-based classification (when no override matches)

1. **PIPELINE evidence** — prompt contains any of: `auth`, `token`, `secret`, `payment`, `crypto`, `password`, `session`, `billing`, `oauth`, `jwt`, `migration`, `schema`, `cross-repo`, `multi-repo`, `critical`.
2. **BUILD evidence** — prompt matches a build/implement/add/create/refactor/migrate verb paired with a feature/endpoint/component/service/caching/layer/dashboard noun, OR names "new endpoint" / "new component" / "new feature", OR references "three/multiple/several files".
3. **Default** — PAIR.

### Fail-safe

An empty or unparseable prompt (or a `gear_select` invocation with no stdin) emits **PIPELINE**, never PAIR — an unevaluable classification input must never silently downshift.

### Persistence

The resolved gear is written to `gear-${sid}` session state (keyed by session id, not PPID — the classifier and every downstream gear-gated hook run as separate subprocesses with different PPIDs). `/harness:intake` and `/harness:pipeline` read this state; neither recomputes it.

## Dispatch matrix

| Phase | PAIR | BUILD | PIPELINE |
|---|---|---|---|
| Plan (architect) | — | light | full |
| Plan Validation | — | `/harness:plan-self-validation` | heavy if `budget>=7`, else `/harness:plan-self-validation` |
| Build | PAIR sub-behaviour (see table above) | single worktree subagent | Best-of-N or PDR-RTV (gated by budget+critical) |
| Polish | — | if `budget>=7` | yes |
| Code Review | reviewer reads diff only (PAIR sub-behaviours that produce a diff) | code-reviewer | code-reviewer + adversarial |
| Security Review | only if hooks touched | only if security-sensitive | yes |
| Final Gate | verify (smoke only) | full 4-agent | full 5-agent (+ spec-blind) |
| Ship (PR) | yes (PAIR sub-behaviours that produce a diff) | yes | yes |
| Deploy | — | conditional | yes |
| Reflect | yes (terse, Haiku, 100 tok cap) | yes | yes |

## Override discipline

| Token in user prompt | Effect | Forensic record |
|---|---|---|
| (default) | Auto-detect via `gear-select.sh` | Gear persisted to `gear-${sid}` |
| "just pair" / "pair on this" | Force PAIR regardless of evidence | Override logged |
| "build it" / "build this properly" | Force BUILD regardless of evidence | Override logged |
| "ship it properly" / "take it all the way" / "full pipeline" | Force PIPELINE regardless of evidence | Override logged |
| User phrasing claims "critical" but gear = PAIR | **Gear wins** at the top level; `critical` still shapes intra-gear dispatch inside BUILD/PIPELINE | — |

## Plan-phase re-classification sanity check

The gear is classified from the user prompt on `UserPromptSubmit`, before the architect's Plan reveals actual scope. If the Plan's affected-files list implies a heavier gear than the one persisted at prompt time, upshift the rest of the pipeline and emit `ROUTING_UPSHIFTED`. Downshifts at this stage are not honoured — once a pipeline is dispatched at BUILD or PIPELINE, it completes at that gear or higher.

Catches the failure mode: user says "tidy up the docs" but architect's plan actually touches 8 source files.

## rules/core.md special handling

`rules/core.md` is load-bearing — every spawn reads it. But not every line in it is equally critical. The principled rule: **the semantic surface matters, not the file**.

| Surface inside `rules/core.md` | Gear floor |
|---|---|
| Iron Laws (numbered 1-8) | **PIPELINE** (Best-of-N + adversarial review mandatory) |
| Code Shape Rules (per-language function limits, CC≤5, nesting≤2 — `protocols/engineering-invariants.md` § Code Shape) | **PIPELINE** |
| Worktree + Commit Protocol section | **BUILD** |
| Pipeline Phase Order text | **BUILD** |
| "Where to Look Next" index (just redirectors) | **PAIR** allowed |

## Quality safety analysis

| Failure mode | Mitigation |
|---|---|
| Auth change classified as PAIR | PIPELINE evidence list includes `auth`, `secret`, `token`, `crypto`, `password`, `session`, `payment`, `billing`, `oauth`, `jwt` — any match forces PIPELINE regardless of other signals |
| Feature classified as PAIR because of phrasing | BUILD/PIPELINE evidence requires positive shape signal (build verb + feature noun, or security keyword); absent that, PAIR is a deliberate default, not a miss |
| Mechanical sweep silently broke behaviour | The batch-pipeline PAIR sub-behaviour still runs diff-only Code Review + smoke-level Final Gate verify — not full behaviour validation, by design |
| Plan got skipped for work that needed it | PIPELINE always runs Plan + Plan Validation. BUILD inherits plan from the user prompt for uniform sweeps (which IS the spec for that shape) |
| Classification hides real complexity | Plan-phase re-classification catches scope creep; upshifts mid-pipeline |

## Interaction with existing protocols

- **Iron Law 5** ("NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.") applies to **BUILD and PIPELINE**. PAIR dispatches outside `/harness:pipeline` and is governed by its own sub-behaviour's verdict catalog entry. This is not an exception to the Iron Law — it is a clarification that the Iron Law's scope is the pipeline, not all work.
- **Iron Law 3** (orchestrator never writes source code; protected-location enforcement via `hooks/_lib/is-protected-path.sh`) governs the PAIR tracked-doc sub-behaviour. Tracked-doc edits route to a lightweight worktree subagent which commits the change with full audit trail.
- **Complexity Budget** still computes (`/harness:intake` Step 2). It controls *intra-gear* dispatch shape (multi-slice Build at BUILD, Best-of-N vs PDR-RTV at PIPELINE). It no longer controls *which* gear.
- **`critical` flag** still computes and shapes intra-gear dispatch (Best-of-N/PDR-RTV eligibility inside PIPELINE).
- **`bestofn` and `pdr_rtv` flags** only fire inside **PIPELINE** AND budget>=7. BUILD forces both flags false regardless of critical or budget. `bestofn` also requires `critical==true`; the `[best-of-n]` override token bypasses the gear+budget gate. SSOT: `hooks/_lib/bestofn_gate.py`.

## Appendix: legacy tier fingerprint detector spec (still consumed by `skills/intake/SKILL.md` Step 1.5)

`skills/intake/SKILL.md` Step 1.5 still runs a tier fingerprint (T0-T6, T3H) and writes `tier_emitted`/`tier_initial` to `intake.md` frontmatter, which `hooks/_lib/intake-fingerprint-emit.py` reads verbatim and appends to `metrics/{session}/intake-overrides.jsonl` forensics. That fingerprint's detector spec — including this canonical safety-override keyword list — lives here because Step 1.5 names this file as its literal source ("Run the regex/glob detectors from `protocols/work-class-routing.md` § Fingerprint Phase 1"). Migrating this appendix requires migrating the hook's field names and its ~45 pinned tests in the same change; deferred to a dedicated wave.

**Canonical safety-override keyword list (lockstep with `skills/intake/SKILL.md` Phase-2 prose):** `auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature`

Phase-2 safety override always wins and upshifts to T4+ regardless of a T3H-shaped match: any of the above keywords appearing in change-target context, or scope touching `hooks/*.sh` body changes, `rules/core.md`/`protocols/atdd-procedure.md`/`protocols/verdict-catalog.md`, any test file, or `auth/*`/`secrets/*`/`*crypto*`/`*.env`.

`round_up_to_T4_when_ANY` contract-eligibility rule (Option-A CONTRACT RULE): a T3H-shaped change rounds up to T4 if it touches an OpenAPI path, a "DB schema", a "public function signature", a "proto", a "cross-repo contract", or a versioned-public schema. An internal JSON shape not published in OpenAPI/Swagger, not proto/event-schema, not versioned/public, and not cross-repo-consumed remains T3H-eligible. When in doubt, round UP.

## Where to look next

| Need | File |
|------|------|
| Gear classifier implementation | `hooks/_lib/gear-select.sh` |
| Complexity Budget dimensions | `protocols/operational-protocol.md` |
| Pipeline phases (BUILD/PIPELINE) | `protocols/pipeline-protocol.md` |
| Parallel dispatch (BUILD/PIPELINE fan-out) | `protocols/parallel-dispatch-protocol.md` |
| Verdicts emitted by intake | `protocols/verdict-catalog.md` § routing entries |
| Legacy tier fingerprint (still live, forensics-coupled, migration deferred) | `skills/intake/SKILL.md` Step 1.5; `hooks/_lib/intake-fingerprint-emit.py` |
| Orchestrator dispatch on gear | `skills/pipeline/SKILL.md` Step 3 |
| PAIR tracked-doc sub-behaviour | Iron Law 3 in `rules/core.md`; `hooks/_lib/is-protected-path.sh` |
