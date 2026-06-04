---
id: instinct-main-moves-mid-pipeline
confidence: 0.55
domain: orchestration
scope: project
roles: [architect, software-engineer, infrastructure-engineer]
source: recurring-observation
created: 2026-06-04T00:00:00Z
evidence_count: 2
last_seen: 2026-06-04T11:27:30Z
---

## Pattern

Main branch can merge new PRs while a Build subagent is running. Before merging or raising a PR from a working branch, always verify the working branch is rebased onto the current `main` HEAD — not the HEAD at worktree creation time.

```bash
# Before raising a PR or triggering Ship:
git -C <worktree> fetch origin main
git -C <worktree> rebase origin/main
# Only then: gh pr create / merge
```

If a long-running subagent ends mid-report without completing, treat the **committed worktree state** (via `git log` / `git show`) as the source of truth for what was built — not the agent's final message, which may be truncated.

## Why

Two confirmed occurrences in this project:

- **guard-hardening-telemetry-fixes (2026-06-04)**: main moved during Build (PR #27 merged while Best-of-N candidates ran). Working branch was rebased onto `18b1dfe` before merge. Scratchpad finding: "main moved during Build — working branch rebased onto 18b1dfe before merge."
- **harden-root-contamination (2026-06-04)**: concurrent session contamination incident; instinct_injector forensics were complicated because root checkout state diverged from expected state mid-pipeline. The session-memory persistent note "Concurrent sessions share the root checkout" captures the wider hazard.

A stale base causes merge conflicts or — worse — silently omits fixes from the earlier-merged PR.

## How to Apply

- **Orchestrator (Ship phase)**: before dispatching the Ship agent, run `git fetch origin main` and compare current working-branch base to `origin/main` HEAD; rebase if they differ
- **Build agents**: after completing all slices, note the current `origin/main` SHA in the scratchpad; if it differs from the worktree base SHA, flag for rebase before merge
- **When a subagent message is truncated**: run `git log --oneline <worktree-branch>` to enumerate committed work; do not assume incomplete agent message = incomplete work
