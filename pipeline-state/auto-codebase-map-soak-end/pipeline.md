---
task_id: auto-codebase-map-soak-end
phase: pending
verdict: pending
timestamp: 2026-05-10T00:00:00Z
not_before: 2026-06-09
classification: refactor
task_class: refactor-harness
budget: 5
critical: false
---

# AUTO-CODEBASE-MAP — DUAL_PATH Soak-End Cleanup

This is a placeholder anchor — DO NOT activate before the `not_before` date.

## Purpose

30 days after auto-codebase-map (Slices A-F) was merged, the DUAL_PATH soak
ends. The reader-fallback branch and any operator-authored manual
`codebase-map.md` files have been visible to operators for a full 30-day
window; if no `codebase-map-divergence.jsonl` hits land in the last 7 days
the soak is considered safe to close. This pipeline:

1. Removes the reader-fallback branch from
   `hooks/_lib/session-memory-read-split.sh` (the `_smr_read_codebase_map`
   helper and its call site). After this slice the reader returns ONLY
   generator output for the codebase-map sub-file.
2. Sweeps `session-memory/{*}/codebase-map.md` files. Each is renamed to
   a `.legacy` sibling (per the C3 migration-script precedent — preserve,
   do not delete), so an operator can rescue any hand-edited content
   before final removal in a later cleanup pass.
3. Asserts no `codebase-map-divergence.jsonl` hits in the last 7 days under
   `metrics/{*}/codebase-map-divergence.jsonl`. Non-zero hits = abort and
   surface to the operator (a project may still be running on the manual
   file path).
4. Updates `rules/_detail/autonomous-intelligence.md` § Sub-file Layout
   & Soak to mark the codebase-map soak as complete (delete the
   codebase-map soak prose; leave the layout-table footnote intact).

The Slice D updater-dispatch refusal is **permanent architecture, not soak
scaffolding** — generator-owned artifacts are off-limits to the
session-memory-updater regardless of soak state. This pipeline does NOT
remove the refusal branch.

## Activation

SessionStart's `_psp_find_active_pipelines` scan surfaces this file as
"soak-end pipeline ready" once today's date passes `not_before`. The
operator (or `/loop`) invokes the pipeline manually — there is no
auto-invocation gate.
