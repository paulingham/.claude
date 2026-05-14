---
name: "plan-cache-lookup"
description: "Plan-phase Stage 0 gate that checks the local plan-template cache for a matching (task_class, repo_hash, tier, critical) key. Slice B ships MISS-only: emits PLAN_CACHE_MISS with a structured reason (no-template, disabled, shadow-mode) and lets the orchestrator fall through to recon + architect. The HIT path (Haiku adapter + structural validator) lands in Slice C. CLAUDE_PLAN_CACHE_MODE defaults to off in Slice B for partial-merge safety; Slice F flips the default to shadow."
verdict: PLAN_CACHE_MISS
phase: plan
dispatch: subagent
---

# Plan Cache Lookup (Slice B — MISS-only)

## What This Skill Does

Stage 0 of Plan Phase Dispatch. Computes a cache key from the current pipeline's task signature and looks for a matching plan template under `learning/{project-hash}/plans/`. In Slice B, every invocation emits `PLAN_CACHE_MISS` with a structured `reason`; the HIT-serving path and its Haiku adapter land in Slice C. The orchestrator MUST fall through to Stage 1 (recon) on MISS — this matches the existing flow exactly and is the partial-merge-safe shape (LOW-eng-3).

## When to Invoke

- Plan phase, BEFORE Stage 1 recon dispatch (the orchestrator wiring lands in Slice D; until then this skill is callable but not yet wired).
- Once per pipeline run. The Plan phase runs once per `/pipeline` invocation, so single-writer concurrency suffices (no flock).
- **Do NOT use when**: `CLAUDE_PLAN_CACHE_MODE=off` (default in Slice B) — the mode resolver short-circuits to `MISS reason=disabled`.

## Inputs

- **Pipeline state**: the active pipeline file located via `_psp_find_active_pipelines` (the canonical pipeline-state reader at `hooks/_lib/pipeline-state-paths.sh`). NEVER use bare `[ -f pipeline-state/$task/$phase.md ]`; the union helper resolves DUAL_PATH layouts (new `pipeline-state/{task}/{phase}.md`, legacy `pipeline-state/{task}-{phase}.md`, and workstream variants).
- **Environment**:
  - `CLAUDE_PLAN_CACHE_MODE` ∈ `{off, shadow, on}`; unset → `off` in Slice B (flipped to `shadow` in Slice F).
  - `CLAUDE_PROJECT_HASH` — env-first override for the cache namespace (mirrors `hooks/observation-capture.sh:30-38`); unset → `_project_hash --fallback "$(basename "$(pwd)")"`.
- **Task signature**: `(task_class, repo_hash, tier, critical)` — the cache key (sha256 of canonical JSON). `repo_hash` is computed by `_repo_hash` (`hooks/_lib/repo-hash.sh`), leaf-content-blind by design (HIGH-eng-1 in plan.md Citation #11).

## Procedure

The skill body sources `hooks/_lib/plan-cache-lookup.sh` and calls one public entry point.

### Step 1 — Resolve mode

Call `_plan_cache_mode`. The resolver:

- Reads `CLAUDE_PLAN_CACHE_MODE`.
- Validates against the closed set `{off, shadow, on}`; any other value (including unset) → `off`.
- This is the hard-default-`off` guarantee of LOW-eng-3: any subset of slices B-E that merges without Slice F STAYS in `off`, so no HIT-serving path can ship by accident.

If mode is `off`, emit `PLAN_CACHE_MISS reason=disabled` and return — no key computation, no filesystem lookup, no audit cost.

### Step 2 — Resolve cache directory

Call `_plan_cache_dir`. Resolution order (env-first, mirroring `hooks/observation-capture.sh:30-38`):

1. `$CLAUDE_PROJECT_HASH` if set and non-empty → `$HOME/learning/$CLAUDE_PROJECT_HASH/plans`.
2. Otherwise → `_project_hash --fallback "$(basename "$(pwd)")"` → `$HOME/learning/<hash>/plans`.

### Step 3 — Compute cache key + look up template

Call `_plan_cache_lookup task_class tier critical`. The function:

1. Calls `_repo_hash` (from `hooks/_lib/repo-hash.sh`) — `sha256(git ls-tree --name-only -r HEAD <stable-dirs>) ⊕ sha256(CLAUDE.md)`.
2. Calls `_plan_cache_key task_class repo_hash tier critical` — sha256 of canonical-JSON `{critical, repo_hash, task_class, tier}` (jq's `-cn --arg` builder fixes key order).
3. Checks `[[ -f "$cache_dir/$key.md" ]]`.
4. Branches:
   - File absent → emit `PLAN_CACHE_MISS reason=no-template`.
   - File present + Slice B (MISS-only) → emit `PLAN_CACHE_MISS reason=shadow-mode`. The HIT path is implemented in Slice C.

### Step 4 — Read pipeline state when callers need task_id

When the orchestrator wires this skill in Slice D, the caller MUST locate the active pipeline file via `_psp_find_active_pipelines` (NOT a bare `[ -f ]` test). The skill body's reference to `_psp_find_active_pipelines` documents this contract — Slice D's wiring will route `task_id`, `task_class`, `tier`, and `critical` into the entry call by reading the active intake/plan state located through this helper.

## Outputs

A single JSON line on stdout:

```
{"verdict":"PLAN_CACHE_MISS","reason":"<reason>","cache_key":"<key-or-empty>"}
```

`<reason>` ∈ `{no-template, disabled, shadow-mode}` in Slice B. Slice C adds `adapter-rejected`, `adapter-pending-stale`, `template-corrupt`. Slice F adds `hash-drift`, `key-mismatch`.

## Verdicts

- `PLAN_CACHE_MISS` (info, plan, emitter=plan-cache-lookup) — always, in Slice B. Continue to Stage 1 recon dispatch.
- `PLAN_CACHE_HIT` — reserved for Slice C; this slice never emits it.

## Failure Modes

- **Missing git repo** → `_repo_hash` returns sha256 of empty input; `_plan_cache_key` still computes a stable key. Subsequent `[ -f ]` will fail → `no-template`. Safe.
- **Missing jq** → `_plan_cache_key` returns non-zero; `_plan_cache_lookup` returns non-zero. Orchestrator MUST treat non-zero exit as MISS (fall through). Slice D wiring spec covers this.
- **`learning/<hash>/plans` directory absent** → `[ -f ]` fails → `no-template`. No `mkdir -p` here; the write side lands in Slice C+F.

## Out of Scope for Slice B

- HIT path / Haiku adapter / structural validator → Slice C.
- Stage 0 orchestrator wiring + Step 2c-bis in `skills/pipeline/SKILL.md` → Slice D.
- `hooks/plan-cache-audit.sh` + `settings.json` PostToolUse entry → Slice E.
- Status line copy + mode default flip `off`→`shadow` → Slice F.
- `/plan-cache-rollout-gate` skill → Slice G.

## References

- Plan: `pipeline-state/plan-cache-agentic/plan.md` § slice-b-skill-miss-only.
- Helper: `hooks/_lib/plan-cache-lookup.sh` (this slice).
- Repo-hash helper: `hooks/_lib/repo-hash.sh` (Slice A).
- Pipeline-state reader: `hooks/_lib/pipeline-state-paths.sh::_psp_find_active_pipelines`.
- Project-hash fallback idiom: `hooks/observation-capture.sh:30-38`.
- Verdict row: `rules/verdict-catalog.md` (`PLAN_CACHE_MISS`).
