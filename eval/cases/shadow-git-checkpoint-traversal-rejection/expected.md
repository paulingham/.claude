# Expected Outcomes (Oracle)

The candidate diff must contain `hooks/_lib/shadow-checkpoint-helpers.sh` with
the `_sgc_validate_id` regex `^[A-Za-z0-9_.-]+$` AND an explicit `..` reject
clause; the `_sgc_ref_name` helper must validate BOTH `task` and `slug`
components before constructing the ref string.

When the test suite is invoked, the following named cases must pass:

1. **AC1.3 _sgc_validate_id rejects traversal segments and separators** —
   `_sgc_validate_id "../etc"`, `_sgc_validate_id ".."`, `_sgc_validate_id
   "a/b"`, and any input containing whitespace or quote characters all return
   non-zero.
2. **AC1.5 _sgc_ref_name rejects invalid task-id** — `_sgc_ref_name "../bad"
   "agent" "0001"` echoes empty + exits 1.
3. **AC1.5 _sgc_ref_name rejects invalid slug** — `_sgc_ref_name "task"
   "agent/.." "0001"` echoes empty + exits 1.
4. **AC2.10 hostile worktree slug containing .. is rejected (no ref outside
   namespace)** — when the resolved worktree basename is `agent-..`, the hook
   exits 0 AND zero refs are created under `refs/checkpoints/`.

Defense in depth: the hostile slug is rejected at TWO layers — first by
`_sgc_validate_id` immediately after `basename "$WT"`, then again by
`_sgc_ref_name` which re-validates both components. Removing either layer
leaves the user-observable invariant intact (no ref created), but keeping both
is the documented intent — a single-layer regression would not be caught at
the `refs/checkpoints/` namespace surface.
