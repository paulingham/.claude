# Expected Outcomes (Oracle)

The candidate diff must contain `hooks/shadow-git-checkpoint.sh`,
`hooks/_lib/shadow-checkpoint-helpers.sh`, the `Write|Edit|NotebookEdit`
matcher block in `settings.json`, and the bats test file
`tests/shell/test_shadow_git_checkpoint.bats`.

When the test suite is invoked via `bats tests/shell/test_shadow_git_checkpoint.bats`,
the following named cases must pass:

1. **AC2.6 happy path creates one checkpoint ref pointing at non-empty tree** —
   after modifying `seed.txt` and firing the hook, exactly 1 ref exists under
   `refs/checkpoints/sgc-test-task/`.
2. **AC2.13 forensic JSONL has canonical keys after happy-path fire** — the
   appended line in `metrics/<session>/shadow-checkpoints.jsonl` parses as JSON
   and contains all 9 canonical keys (`ts, hook, task_id, worktree_slug, step,
   ref, sha, duration_ms, success`).
3. **AC2.7 clean worktree (no changes to stash) emits no ref** — when the
   worktree is at HEAD with no diff, the same hook fire produces 0 refs (proves
   the happy-path test is genuinely producing the ref, not accidentally on every
   fire).

The Iron Law 4 invariant must hold throughout: REPO_ROOT HEAD remains on `main`,
and every `git` invocation in `hooks/shadow-git-checkpoint.sh` and
`hooks/_lib/shadow-checkpoint-helpers.sh` uses `git -C "$WT"` delegation
(verified by `pytest tests/test_shadow_git_checkpoint.py::test_ac28_all_git_invocations_use_dash_C_delegation`).
