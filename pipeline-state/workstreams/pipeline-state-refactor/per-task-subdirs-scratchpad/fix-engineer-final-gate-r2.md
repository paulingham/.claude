---
category: decision
---

# fix-engineer-final-gate-r2 — per-task-subdirs round 2

Three Final Gate findings addressed on `fix/pipeline-state-refactor/final-gate-findings-r2`, branched from integration tip `ada6955`.

## Finding 1 — `CLAUDE.md` SessionStart stale glob (MEDIUM, in-cycle)

**Decision**: replace the legacy glob with a sourced helper invocation.

**Why**: `pipeline-state/*-pipeline.md` only matches the legacy flat layout. After the per-task-subdirs refactor, in-flight pipelines also live at `pipeline-state/{task-id}/pipeline.md` and under `pipeline-state/workstreams/{ws}/{task-id}/pipeline.md`. The orchestrator would silently miss those on session resume — exactly the regression Slice A was meant to prevent. `_psp_find_active_pipelines` from `hooks/_lib/pipeline-state-paths.sh` already unions all four globs and is the canonical discovery surface elsewhere in the harness; reusing it avoids duplicating the glob list in prose.

**How to apply**: any future docs that need to enumerate active pipelines must reference the helper, not literal globs. Inline glob-list alternatives are brittle to layout evolution.

## Finding 2 — `_cf_pipeline_id` body grew beyond the file's stated `<=5` invariant (MEDIUM)

**Decision**: extract the layout-aware path-parsing into a sibling helper `_cf_pipeline_id_from_path` in the same file.

**Why**: Slice B legitimately added a 4-line case statement to `_cf_pipeline_id` to handle both layouts (`{task}/pipeline.md` vs `{task}-pipeline.md`). That pushed the body from 5 lines to 8 — silently violating the file's header invariant ("Every function body <=5 lines") and breaking T18 in `tests/shell/test_cost_feed.bats`.

**Extraction over inline-comment-deletion**: Slice B's case statement is meaningfully testable independently of the discovery side effect (the helper takes a path and returns a task-id). Extracting it keeps `_cf_pipeline_id` small AND gives Slice B's path-parsing logic a stable name. Trimming comments inside `_cf_pipeline_id` would have been a code-smell fix (5 = 5) without the testability win.

**Sibling-file rejected**: `cost-helpers.sh` is 50 LOC after extraction (4 LOC added — well under the 50-line cap; T17 only checks the hook file, not the helpers). No need to spill into a new file.

**How to apply**: when a body that already does one thing grows past 5 lines because a NEW concept got introduced, extract the new concept by name. Don't shrink comments to game the line count.

## Finding 3 — `resource-bounds-docs.bats` T4.6 — RETIRED (LOW, in-cycle)

**Decision**: retire (delete) the assertion, leaving an explanatory comment block in its place.

**Why retire vs amend**: the assertion was a wave1-B-specific guard. Its stated scope (per session memory) was `rules/agent-protocol.md` and `rules/parallel-dispatch-protocol.md` during the resource-bounds-protocol additive layering. That period has long since concluded. The per-task-subdirs refactor's deletions in those two files (path-format updates from `{task}-scratchpad/` to `{task}/scratchpad/`) are intentional and correct — they're the whole point of Slice A. Amending T4.6 to anchor sentences would re-encode the same brittleness for a non-load-bearing concern, and would also fail to capture the additional deletions in `pipeline-protocol.md` and `autonomous-intelligence.md` that Slice A intentionally rewrote.

**Replacement coverage**: T4.1, T4.2, T4.5, T4.7, T4.8 all pin the load-bearing wave1-B anchors (`## Resource Bounds` H2, `CLAUDE_SUBAGENT_DEPTH=` assignment, `Subagent depth: {N}` context line). Anchor-based assertions are how the wave1-B contract should have been pinned from the start. The numstat-based "zero deletions" approach was a structural assertion that was always going to break as soon as documentation evolved — even outside the per-task-subdirs work.

**How to apply**: never use `git diff --numstat = 0` as a regression guard against documentation evolution. Pin the anchors that are load-bearing instead. The retired test's comment block left in-place documents the rationale for the retirement so future maintainers don't reintroduce the pattern.

## Verification

| Test | Before fix-r2 | After fix-r2 |
|---|---|---|
| `test_cost_feed.bats T18` (body <=5 lines) | not ok | ok |
| `test_cost_feed.bats T6` (legacy mtime resolution) | not ok | not ok (pre-existing — pipeline-state legacy semantics, unrelated to fix-r2) |
| `test_cost_feed.bats T19` (shellcheck SC1090) | not ok | not ok (pre-existing — unrelated) |
| `test_cost_helpers_new_layout.sh` | ok | ok (Slice B contract preserved) |
| `resource-bounds-docs.bats` | 1 fail / 7 pass | 7 pass (T4.6 retired) |
| `tests/test_pre_agent_allowlist.py` | 8 fail | 8 fail (pre-existing — Path-B advisory hook, unrelated to fix-r2) |
| `tests/test_settings_portability.py` | 1 fail | 1 fail (pre-existing — unrelated to fix-r2) |

All three findings cleanly addressed. No collateral damage.

## Audit artifacts

- `pipeline-state/workstreams/pipeline-state-refactor/per-task-subdirs-fix-r2-red.txt`
- `pipeline-state/workstreams/pipeline-state-refactor/per-task-subdirs-fix-r2-green.txt`
