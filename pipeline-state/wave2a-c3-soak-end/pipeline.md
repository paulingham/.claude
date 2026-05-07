---
task_id: wave2a-c3-soak-end
phase: pending
verdict: pending
timestamp: 2026-05-07T00:00:00Z
not_before: 2026-06-06
classification: refactor
task_class: refactor-harness
budget: 5
critical: false
---

# WAVE 2a-C3 — Session Memory Split, Soak-End Cleanup

This is a placeholder anchor — DO NOT activate before the `not_before` date.

## Purpose

30 days after wave2a-c3-session-memory-split was merged, the DUAL_PATH soak
ends. This pipeline:

1. Removes the reader-fallback code path:
   - `hooks/_lib/session-memory-read-split.sh`'s legacy branch in `session_memory_read_split`
   - Any soak-window comments referencing `notes.md.legacy` discovery
2. Sweeps `session-memory/{*}/notes.md.legacy` files. Reports any with hand-edited
   non-canonical headers (those would have emitted stderr warnings during migration)
   so an operator can rescue content before deletion.
3. Removes `notes.md.legacy.{ts}` archives after operator review.
4. Asserts no `session-memory-read-fallback` JSONL lines have appeared in the
   last 7 days under `metrics/{*}/session-store-mirror.jsonl`. Non-zero =
   abort and surface to the operator (a project is still running on legacy).
5. Updates `rules/_detail/autonomous-intelligence.md` § Sub-file Layout & Soak
   to mark the soak as complete (delete the soak section, leave the layout
   section).

## Activation

SessionStart's `_psp_find_active_pipelines` scan surfaces this file as
"soak-end pipeline ready" once today's date passes `not_before`. The
operator (or `/loop`) invokes the pipeline manually — there is no
auto-invocation gate.
