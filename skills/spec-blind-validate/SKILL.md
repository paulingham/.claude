---
name: spec-blind-validate
description: "Final-Gate teammate that authors black-box behavioural tests from the AC plan + public API surface ONLY — never from src/. Catches the SWE-Bench-Pro-vs-Verified failure mode. Read/Bash content-leak shapes are blocked by three PreToolUse hooks (read-guard, write-guard, bash-guard). Invoked in parallel with /harness:verify, /harness:qa-test-strategy, /harness:product-acceptance, /harness:patch-critique."
verdict: SPEC_BLIND_VALIDATED|SPEC_BLIND_FAILED|SPEC_BLIND_INSUFFICIENT_SURFACE|SPEC_BLIND_BLOCKED
phase: final-gate
dispatch: subagent
agent: spec-blind-validator
---

# Spec-Blind Validate

## What This Skill Does

Adds a **fifth Final Gate teammate** that authors tests against the public API contract from the AC plan ONLY — without ever seeing implementation source. Three PreToolUse hooks (`hooks/spec-blind-read-guard.sh`, `hooks/spec-blind-write-guard.sh`, `hooks/spec-blind-bash-guard.sh`) enforce the constraint by exiting 2 on any read attempt outside the public-surface allowlist, any write outside test directories, and any Bash content-leak shape (`cat`/`head`/`tail`/`sed`/`awk`/`xxd`/`hexdump`/`node -e`/`python -c`/`ruby -e`/`perl -e`/`grep -r src/`/`find src/`) that would bypass the read-guard.

The "second body of tests" is the value-add: spec-blind tests pass + build-time tests pass + same observable behaviour ⇒ cross-validated coverage. Spec-blind fails + build-time passes ⇒ SWE-Bench-Pro failure mode caught (build's tests codify the same misconception as production code).

## When to Invoke

- Final Gate phase, in parallel with `/harness:verify`, `/harness:qa-test-strategy`, `/harness:product-acceptance`, `/harness:patch-critique`
- After `/harness:code-review` and `/harness:security-review` both APPROVED (Build phase complete)
- All five Final Gate teammates run independently against the same final state — no lock contention

## Inputs

The orchestrator hands the spawned agent these inputs in the prompt:

| Input | Source |
|-------|--------|
| AC list | `$state_dir/{task-id}/plan.md` § Acceptance Criteria (verbatim — NEVER the diff) |
| Intake spec | `$state_dir/{task-id}/intake.md` (user's verbatim spec) |
| Recursion-guard precheck result | from `is_harness_internal_cwd` invocation in step 1 of § Process below |
| AC form annotation | ACs may carry a `form:` tag (e.g. `form: ears-event`); an EARS clause maps trigger→arrange, response→assert; no read-model change — the verbatim AC line is still the oracle source |

**The agent NEVER receives `git diff main...HEAD`.** That is the patch-critic's input, not this gate's. Independence from implementation is the design.

## Public API Surface (convention-based — the validator's read allowlist)

The path-allowlist is established by `hooks/_lib/spec-blind-allow-paths.{sh,txt}` and consumed by all three guards.

| Glob | Source / rationale |
|---|---|
| `$state_dir/{task-id}/plan.md` | The AC list IS the spec — primary input |
| `$state_dir/{task-id}/intake.md` | User's verbatim spec — secondary input |
| `**/interface.{ts,tsx,js,jsx,rb,py,go,rs,java,kt,swift}` | `protocols/module-boundaries-protocol.md` § Module Contract Artifacts |
| `**/types.{ts,tsx,js,jsx,rb,py,go,rs,java,kt,swift}` | Same source, optional artifact |
| `**/events.{ts,tsx,js,jsx,rb,py,go,rs,java,kt,swift}` | Same source, optional artifact |
| `**/index.{ts,tsx,js,jsx,mjs,cjs}` | Node convention barrel-export entry point |
| `**/__init__.py` | Python convention package entry point |
| `**/lib.rs`, `**/mod.rs` | Rust convention crate/module entry point |
| `**/*.h`, `**/*.hpp` | C/C++ convention public header |
| `**/README.md` | Module documentation |
| `**/*.openapi.{yaml,yml,json}` | OpenAPI contracts |
| `**/*.proto` | Protobuf contracts |
| `**/schemas/*.json` | JSON-Schema contracts |
| `CLAUDE.md`, `.claude/CLAUDE.md` | Test-runner discovery |
| `package.json`, `Gemfile`, `pyproject.toml`, `Cargo.toml`, `go.mod` | Test-runner discovery — convention manifests |
| `tests/**`, `test/**`, `spec/**`, `__tests__/**` | The validator's OWN authored tests |

**Denied (concrete examples)**: `src/**`, `lib/**` (except language-canonical entry-point files above), `app/**`, `internal/**`, `cmd/**`, `pkg/**`, `bin/**`, `dist/**`, `build/**`, `node_modules/**`, `vendor/**`. Default-deny.

## Recursion Guard

When the project repo IS the harness itself (i.e. cwd resolves to `${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}`), the validator emits `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `harness-internal-recursion` and exits before any read attempt. The harness has no `interface.{ext}` or `index.{ext}` of its own (it ships hooks, skills, agents, and protocol .md files), so authoring spec-blind tests against the harness would either leak hook source via the test-runner shell or produce no signal.

The recursion-detection helper lives at `hooks/_lib/spec-blind-recursion.sh` and exposes `is_harness_internal_cwd <cwd>`. Detection requires BOTH:

1. `${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/rules/core.md` exists, AND
2. `realpath($(git -C <cwd> rev-parse --show-toplevel))` equals `realpath(${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}})`.

The `git remote` heuristic was considered and dropped — it is fragile across forks, mirrors, and stale remotes.

## Fix-Engineer Constraint

On `SPEC_BLIND_FAILED`, the orchestrator dispatches `fix-engineer` per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule. The fix-engineer is **code-fix-only on this verdict** — it MUST NOT mutate ACs. The AC list is the contract; if the candidate build's behaviour disagrees with the AC literal, the build is wrong (not the AC). If the AC itself is wrong (a Plan-phase defect surfacing late), fix-engineer surfaces back to the orchestrator with a HALT recommendation; the orchestrator must escalate to the user for a Plan revision.

## Process

> **Subagent-type resolution (SEC-MED-2).** All three guards (read / write / bash) resolve `subagent_type` via this fallback chain: (1) the `.subagent_type` top-level field on the PreToolUse JSON envelope, (2) the `CLAUDE_SUBAGENT_TYPE` environment variable. The orchestrator MUST set `CLAUDE_SUBAGENT_TYPE=spec-blind-validator` in the spawn shell when dispatching this validator so the guards still fire even if the harness omits the JSON field. Mirrors the precedent at `hooks/cost-feed.sh:33`.

1. **Recursion-guard precheck (BEFORE any Read)**: source `hooks/_lib/spec-blind-recursion.sh` and call `is_harness_internal_cwd "$(pwd)"`. If the helper returns 0 (harness-internal), emit `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `harness-internal-recursion` and exit. This invocation MUST precede the first Read step — without the precheck, V1 would attempt to author spec-blind tests against the harness itself.
2. **Read inputs**: Read the AC list (`$state_dir/{task-id}/plan.md`) and intake spec (`$state_dir/{task-id}/intake.md`).
3. **Discover public surface**: Glob the public-surface allowlist. If nothing matches (no `interface.*`, no `index.*`, no `__init__.py`, no OpenAPI/Protobuf/JSON-Schema), emit `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `no-public-surface-discoverable`.
4. **Read public surface**: Read each discovered artifact. The read-guard hook will exit 2 on any read attempt outside the allowlist; if your read fails, the path is denied — choose a public-surface alternative.
5. **Author behavioural tests**: Write tests under `tests/`, `test/`, `spec/`, or `__tests__/`. Each test MUST import only from public-surface paths or test-only fixtures. Imports of `src/handlers/foo` etc. are forbidden by convention even if not blocked at the hook layer.
6. **Discover test runner**: Read `CLAUDE.md` and the convention manifests (`package.json`, `Gemfile`, `pyproject.toml`, `Cargo.toml`, `go.mod`). Match against the **finite enumerated test-runner ladder** — exactly seven entries, allowlisted at `hooks/_lib/spec-blind-test-runners.txt`:
   - `npm test`
   - `pnpm test`
   - `yarn test`
   - `bundle exec rspec`
   - `pytest`
   - `cargo test`
   - `go test`

   If none match, emit `SPEC_BLIND_INSUFFICIENT_SURFACE` with reason `no-test-runner-discoverable`.
7. **Run the tests**: invoke the discovered runner via Bash (allowed by `hooks/spec-blind-bash-guard.sh`). Capture output.
8. **Emit verdict**:
   - All tests green → `SPEC_BLIND_VALIDATED`.
   - Any test red → `SPEC_BLIND_FAILED` (cite failing assertion's AC number + observed-vs-expected).
   - Any hook block, harness error, or timeout that prevents the run → `SPEC_BLIND_BLOCKED` (HALT — operator escalation).

## Verdicts

- **SPEC_BLIND_VALIDATED** (success) — pipeline advances to next gate.
- **SPEC_BLIND_FAILED** (failure) — fix-engineer dispatched (code-fix-only; MUST NOT mutate ACs).
- **SPEC_BLIND_INSUFFICIENT_SURFACE** (info) — pipeline advances; Final Gate summary renders `spec-blind: SKIPPED (no public surface)`.
- **SPEC_BLIND_BLOCKED** (failure) — HALT pipeline + emit operator-visible escalation.

## Future Work (V2 placeholder — see `$state_dir/spec-blind-validator-harness-aware-soak-end/pipeline.md`)

V1 emits `SPEC_BLIND_INSUFFICIENT_SURFACE` for harness-internal pipelines. V2 will augment the allowlist to make spec-blind validation viable on the harness itself. Specifically, V2 will add:

- `protocols/**.md` — harness contract surface (the iron laws + protocol detail are the harness's own "public API")
- `agents/*.md` — agent frontmatter + role definitions (the public surface for orchestrator dispatch)
- `skills/**/SKILL.md` — skill frontmatter contracts (verdicts + dispatch shape)
- `orchestrator/**.md` — orchestrator-side procedure detail
- `CLAUDE.md` — top-level harness contract
- `hooks/_lib/**.txt` — sibling-file allowlists (e.g. `destructive-verbs.txt`, `spec-blind-test-runners.txt`)

Sources under `hooks/*.sh` and `hooks/_lib/*.sh` remain deny — they are implementation, not contract.

The placeholder pipeline `$state_dir/spec-blind-validator-harness-aware-soak-end/pipeline.md` carries a `not_before:` calendar anchor pinned 30 days post-merge of V1; SessionStart's active-pipeline scan surfaces it once the date passes.

## Anti-Patterns

- Reading `src/` "just to understand the data shape" — the hook blocks; the interface file IS the data shape.
- Authoring a test that imports `../src/handlers/foo` — even if not hook-blocked, the test is invalid (the validator's value depends on import-blindness).
- Bypassing the test-runner allowlist with a custom shell command — emit `SPEC_BLIND_INSUFFICIENT_SURFACE` (`no-test-runner-discoverable`) instead.
- Filing a "fix in next pipeline" follow-up on `SPEC_BLIND_FAILED` — the In-Cycle Fix Rule applies; fix-engineer runs in this pipeline.
