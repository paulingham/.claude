---
name: "plan-cache-lookup"
description: "Plan-phase Stage 0 gate that checks the local plan-template cache for a matching (task_class, repo_hash, tier, critical) key. Slice B ships MISS-only: emits PLAN_CACHE_MISS with a structured reason (no-template, disabled, shadow-mode) and lets the orchestrator fall through to recon + architect. The HIT path (Haiku adapter + structural validator) lands in Slice C. CLAUDE_PLAN_CACHE_MODE defaults to off in Slice B for partial-merge safety; Slice F flips the default to shadow."
verdict: PLAN_CACHE_MISS
phase: plan
dispatch: subagent
---

# Plan Cache Lookup (Slice B MISS path + Slice C HIT path)

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
4. Branches (this `_plan_cache_lookup` entry point covers the off / shadow-mode branches only; the on-mode HIT path is in place in Slice C and is driven by the orchestrator via the four steps in § HIT Path Dispatch below — NOT through this lookup function):
   - File absent → emit `PLAN_CACHE_MISS reason=no-template`.
   - File present + mode ∈ {off, shadow} → emit `PLAN_CACHE_MISS reason=shadow-mode` (mode=off was already short-circuited at Step 1; this branch is reached only in shadow). See § HIT Path Dispatch for the on-mode flow.

### Step 4 — Read pipeline state when callers need task_id

When the orchestrator wires this skill in Slice D, the caller MUST locate the active pipeline file via `_psp_find_active_pipelines` (NOT a bare `[ -f ]` test). The skill body's reference to `_psp_find_active_pipelines` documents this contract — Slice D's wiring will route `task_id`, `task_class`, `tier`, and `critical` into the entry call by reading the active intake/plan state located through this helper.

## HIT Path Dispatch

On a key match (mode=`on`, template present), the skill performs four
single-shot steps. On validator rejection the path falls through in-cycle to
Stage 1+2 per Iron Law 6; the adapter is not re-invoked in this pipeline.

1. Mutate template frontmatter via `_plan_cache_write_pending TEMPLATE`
   (tmp+mv atomic). Sets `last_adapted_at=now()` and
   `last_adapt_outcome=pending` BEFORE adapter spawn (state-before-expensive-op,
   Memory M5). Crash mid-adapter leaves the `pending` marker on disk so the
   next entry treats the template as stale.
2. Write the resume-safety stub via `_plan_cache_write_resume_stub TASK_ID`
   (AC C8). Creates `pipeline-state/{task-id}/architect-context.md` with
   body `<!-- cache_hit: true, recon-skipped -->` so `/pipeline-resume`
   readers don't stall on the missing recon output.
3. Spawn the adapter agent (one Agent directive — single-shot, no loop):

```
Agent({
  subagent_type: "plan-cache-adapter",
  model: "haiku",
  maxTurns: 8,
  prompt: "Read ~/.claude/agents/plan-cache-adapter.md.
    Cached template: {template-path}.
    Current ACs: {ACs from pipeline-state/{task-id}/intake.md}.
    Write adapted plan to pipeline-state/{task-id}/plan.md with `cache_hit: true`
    in the frontmatter and preserve the four required H2 sections:
    ## Slices, ## Alternatives Considered, ## Codebase Ground-Truth Citations,
    ## Pre-Mortem."
})
```

4. Call `_plan_cache_finalize TEMPLATE PLAN KEY`.
   Pass → flips outcome=success, emits `PLAN_CACHE_HIT`.
   Reject → DELETES the produced plan.md, flips outcome=failed, appends both
   `verdict=PLAN_CACHE_MISS reason=adapter-rejected` and
   `event=PLAN_CACHE_FALLTHROUGH` to `metrics/{session}/plan-cache.jsonl`,
   emits `PLAN_CACHE_MISS reason=adapter-rejected`. The orchestrator MUST then
   run Stage 1+2 in the same pipeline (Iron Law 6: no deferral, no follow-up).

## Outputs

A single line on stdout, prefixed with the audit-hook marker
`[PlanCacheLookup]` so the universal-PostToolUse sibling at
`hooks/plan-cache-audit.sh` (Slice E) can identify and parse it:

```
[PlanCacheLookup] {"verdict":"PLAN_CACHE_MISS","reason":"<reason>","cache_key":"<key-or-empty>"}
```

or, on HIT:

```
[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"<key>"}
```

`<reason>` ∈ `{no-template, disabled, shadow-mode}` in Slice B; Slice C adds `adapter-rejected`, `adapter-pending-stale`, `template-corrupt`. Slice F adds `hash-drift`, `key-mismatch`.

## Status Line Copy (Slice F)

Each verdict pairs the `[PlanCacheLookup]` JSON audit marker with one
user-facing console line (or stays silent). Strings below are VERBATIM
per `pipeline-state/plan-cache-agentic/plan.md` § Status Line Copy and are
emitted by `_plan_cache_status_line` (`hooks/_lib/plan-cache-lookup.sh`).

| State | Console string |
|---|---|
| MISS reason=`shadow-mode` | `[plan-cache] shadow-mode active (cache observable, not serving) — recon+architect running as normal` |
| MISS reason=`no-template` | `[plan-cache] no cached plan for this task signature — recon+architect running as normal` |
| MISS reason=`disabled` | (silent — no console line; JSON marker only) |
| HIT served | `[plan-cache] cache HIT — Haiku adapted in {N}s, estimated savings ~${cost}; verify slices against current repo before Build` |
| MISS reason=`adapter-rejected` | `[plan-cache] adapter output rejected by validator — falling through to recon+architect in this pipeline (Iron Law 6)` |

`{N}` and `{cost}` are interpolated from `CLAUDE_PLAN_CACHE_ADAPT_SECS`
and `CLAUDE_PLAN_CACHE_SAVINGS_USD` (set by the orchestrator wiring around
the adapter spawn).

## Verdicts

- `PLAN_CACHE_MISS` (info, plan, emitter=plan-cache-lookup) — fall through to Stage 1 recon + Stage 2 architect in the same pipeline (Iron Law 6 on `adapter-rejected`).
- `PLAN_CACHE_HIT` (info, plan, emitter=plan-cache-lookup) — adapted plan written to `pipeline-state/{task-id}/plan.md` with `cache_hit: true` marker; skip Stage 1+2.

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

- Plan: `pipeline-state/plan-cache-agentic/plan.md` § Slice slice-b-skill-miss-only and § Slice slice-c-adapter-and-validator.
- Helper: `hooks/_lib/plan-cache-lookup.sh` (Slice B + Slice C functions).
- Repo-hash helper: `hooks/_lib/repo-hash.sh` (Slice A).
- Adapter agent: `agents/plan-cache-adapter.md` (Slice C).
- Pipeline-state reader: `hooks/_lib/pipeline-state-paths.sh::_psp_find_active_pipelines`.
- Project-hash fallback idiom: `hooks/observation-capture.sh:30-38`.
- Verdict rows: `rules/verdict-catalog.md` (`PLAN_CACHE_MISS`, `PLAN_CACHE_HIT`).
