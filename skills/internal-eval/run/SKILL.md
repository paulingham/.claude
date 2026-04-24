---
name: "internal-eval-run"
description: "Sub-skill of /internal-eval. Executes the inner pipeline per case under full isolation. Populated by Story 6 (runner) and Story 7 (harness-ref pinning via shadow HOME or CLAUDE_HARNESS_ROOT)."
context: fork
agent: software-engineer
---

# Internal Eval — Run

## Status

Stub. Populated by Story 6 (per-case runner with timeout + cost ceiling + dry-run + status enum) and Story 7 (`--harness-ref` via `git worktree add <sha>` and shadow HOME so skills/hooks/rules resolve from the pinned SHA, not live `~/.claude`).

## Purpose

For each case in the suite, spawn an inner `/pipeline` that implements the case's prompt, capture the produced diff + test results, and write `eval/runs/{run-id}/cases/{case-id}/result.json`. Isolation is the hard part — see `ISOLATION.md` (created in Story 6a).

## Isolation Contract (Story 6a)

Every inner pipeline inherits these env vars — they keep inner runs from contaminating outer state:

| Variable | Purpose |
|---|---|
| `CLAUDE_PIPELINE_TASK_ID=eval-{run-id}-{case-id}` | Inner task-id namespace for trajectory + state files |
| `CLAUDE_PIPELINE_BYPASS=1` | Lets `pipeline-state-guard.sh` permit inner writes without an outer pipeline match |
| `CLAUDE_DISABLE_AUTO_LEARN=1` | Suppresses auto-learn-gate firings from inner runs |
| `CLAUDE_PROJECT_HASH=<eval-specific>` | Inner observations + session-memory land in their own namespace |
| `HOME=<shadow-root>` or `CLAUDE_HARNESS_ROOT` | Pins skill/hook/rule resolution to the harness SHA, not live `~/.claude` |
| `EVAL_RUN_ID`, `EVAL_CASE_ID` | Cost attribution tags |

Inner state lives under `eval/runs/{run-id}/inner/`, not shared `pipeline-state/`. Teardown leaves zero residue.

## Per-Case Status Enum (Story 6, B4/B6)

- `passed` — diff matches oracle
- `failed_diff` — ran to completion but diff mismatch
- `failed_build` — inner pipeline aborted at BUILD
- `failed_timeout` — wall-clock limit exceeded
- `failed_infra` — harness-side failure (never counts as regression)

## Verdict

Populated by Story 6. Per-case verdicts above; suite-level verdict is emitted by the parent `/internal-eval` skill.
