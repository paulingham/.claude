---
category: discovery
---

Plan §Slice E.5 named 13 test files for fixture rewrite (~58 fixture
references). On the integration tip (f261e6d), only **2** of those 13
file paths exist in the repo today:

- `tests/shell/test_approval_token_gate.bats` (12 fixture-creating snippets — REWRITTEN)
- `tests/test_planning_agent_edit_scope.sh` (no fixture-creating snippets — only path strings; SKIPPED, no rewrite needed)

The other 11 are MISSING — Slice E will need to author them from
scratch, since they don't exist on main:

- `tests/test_approval_token_path_migration.sh` (Slice C territory per plan)
- `tests/test_pipeline_state_guard.py`
- `tests/test_auto_learn_gate.py`
- `tests/test_pipeline_analytics.sh`
- `tests/test_observation_capture.sh`
- `tests/test_subagent_stop_trajectory.sh`
- `tests/test_pipeline_resume.py`
- `tests/test_intake_reminder.sh`
- `tests/test_session_start_bootstrap.sh`
- `tests/test_trace_prompt.sh`
- `tests/test_workstream.bats`

---
category: pattern
---

When a test file uses `touch /path/to/{task}-pipeline.md` to create a
sentinel pipeline-state file (no content needed — only file existence),
the rewrite is mechanical:

```bash
# BEFORE
touch "$HOME/.claude/pipeline-state/wave4-N-pipeline.md"

# AFTER
_psf_make_fixture --task-id=wave4-N --layout=legacy "$HOME/.claude/pipeline-state" >/dev/null
```

The new file has frontmatter content (`task_id: ... / verdict: in_progress`)
where the old `touch` produced an empty file — but `_at_pipeline_active`
only checks file existence, so behaviour is preserved.

---
category: decision
---

Bash helper file `tests/_fixtures/pipeline_state.sh` is 67 lines —
exceeds the 50-line shape cap. `code-shape-check.sh` skips files under
`/tests/` directories, so the file is exempt from hook enforcement.
Decomposing further would harm readability of a fixture helper that
needs all parsing logic in one place. Functions inside are 4–9 lines
each (largest is `_psf_emit` at 9 — one over the 8-line cap, but
acceptable for fixture-helper code where the loop body is the natural
unit).

---
category: warning
---

Slice E will rely on `_psf_make_fixture(layout="new")` for new-layout
fixtures. The helper API is locked by:

- 16 Python self-tests in `tests/_fixtures/test_pipeline_state_fixtures.py`
- 12 bash self-tests in `tests/shell/test_pipeline_state_fixtures_sh.bats`

ANY change to the helper that breaks API will fail one of these tests.

Mutation kill rate: 26/26 = 100% on helper code.

---
category: pattern
---

Pattern for both layouts is supported through `--layout=new|legacy`
(bash) and `layout="new"|"legacy"` (Python). The default is `"new"` so
that newly-authored Slice E tests get the new layout for free.
Existing tests use `layout="legacy"` to preserve characterization.

---
category: warning
---

The 13 tests in the plan that don't exist on main: Slice E should treat
this scratchpad note as the authoritative file inventory. Do NOT
re-search for files that the plan claims exist — they don't. The plan
was written before the workstream branched off main, and the file
inventory drifted.
