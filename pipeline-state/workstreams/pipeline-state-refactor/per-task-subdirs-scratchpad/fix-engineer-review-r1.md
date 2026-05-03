---
category: decision
---

Fix-engineer Round 1 — addressed all 11 in-cycle findings from code-reviewer
(8 MEDIUM) and security-engineer (2 HIGH + 1 test gap). No findings disputed.
No out-of-scope items touched.

## Findings addressed

- **1-6 (doc path drift)**: Aligned five rule/orchestrator files with the
  per-task-subdir layout. `pipeline-state/{task-id}-scratchpad/` →
  `pipeline-state/{task-id}/scratchpad/`; same for `-best-of-n.md`.
- **5 (Reflect cleanup widening)**: `reflection-protocol.md` § 6d now requires
  cleanup of BOTH new-layout and legacy scratchpad forms during the DUAL_PATH
  soak, with a pointer to `skills/pipeline/SKILL.md` § 7d for the canonical
  `_psp_phase_list`-based snippet (avoids bare-glob prefix collisions).
- **7-8 (hook glob exclusion drift)**: `pipeline-state-guard.sh` and
  `intake-reminder.sh` replaced inline `find` with `_psp_find_active_pipelines`,
  which delegates to `find_pipeline_files` and inherits the
  `EXCLUDED_ROOT_DIRS = {workstreams, health-reports}` exclusion. New
  assertion `guard_blocks_when_only_health_reports_pipeline_exists` locks the
  exclusion in place.
- **9-10 (path-traversal regex)**: Tightened approval-token regex to require
  the first character be alnum/underscore/hyphen
  (`^[A-Za-z0-9_-][A-Za-z0-9_.-]*$`). Rejects `..`, `.foo`. Verified existing
  task_ids (`tool-timing-capture`, `wave4-S`, `audit-sonnet-context-200k`,
  `per-task-subdirs`) all match.
- **11 (test gap)**: Added `write_approval_token_rejects_dotdot_task_id` to
  `tests/test_approval_token_path_migration.sh`. RED captured (test catches
  bug — traversal landing pad created at $HOME/.claude/approval.token), then
  regex tightening turned it GREEN.

## Out-of-scope (intentionally untouched)

The 4 LOW security findings + 2 pre-existing issues listed in the fix prompt
were left alone. Pre-existing `_at_resolve_task_id` workstream-branch task_id
mismatch is tracked in plan Follow-up #3 — not exacerbated by this refactor.

## Notes for reviewer

- The two pre-existing failures in `tests/shell/test_approval_token_gate.bats`
  (test 1 `_at_token_path: returns expected path under HOME`, test 22
  `write-approval-token.sh: writes token file with given verdict`) predate
  this fix branch (verified by `git stash` + re-run on integration HEAD).
  They expect the legacy hyphenated form and have not been migrated to the
  new layout. They are NOT in scope for r1.
- Helper `_psp_find_active_pipelines` is sourced via
  `~/.claude/hooks/_lib/pipeline-state-paths.sh`. Tests run with `HOME=$TMP`,
  which routes the source to the symlinked `$TMP/.claude/hooks/_lib/...` —
  works because the existing dual-path tests already use this pattern.

## Audit artifacts

- RED:   `pipeline-state/workstreams/pipeline-state-refactor/per-task-subdirs-fix-r1-red.txt`
- GREEN: `pipeline-state/workstreams/pipeline-state-refactor/per-task-subdirs-fix-r1-green.txt`
