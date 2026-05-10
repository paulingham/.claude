# shadow-git-checkpoint — happy-path capture

## Problem

A PostToolUse hook (`hooks/shadow-git-checkpoint.sh`) is configured to fire on
`Write|Edit|NotebookEdit` and capture the active worktree's pending changes to a
hidden ref `refs/checkpoints/{task-id}/{worktree-slug}-{step}` after every
file-mutating tool call inside an active pipeline's worktree.

This case verifies the **happy path**: when a build agent edits a source file
inside a real worktree and an active pipeline state file declares the task-id,
the hook produces exactly one new ref under the task's checkpoint namespace
pointing at a non-empty git tree.

## Acceptance Criteria

- A worktree exists at `<TMP>/.claude/worktrees/agent-test/` with a single
  committed file `seed.txt` (initial content `seed\n`).
- An active pipeline state file exists at
  `<TMP>/.claude/pipeline-state/sgc-test-task/pipeline.md` with frontmatter:
  `task_id: sgc-test-task`, `verdict: in_progress`.
- After modifying `seed.txt` inside the worktree and firing the hook with
  payload `{tool_name:"Write",tool_input:{file_path:"<WT>/seed.txt"}}`:
  - The hook exits 0.
  - Exactly one ref exists under `refs/checkpoints/sgc-test-task/` in the
    worktree's git ref database.
  - The ref name follows the canonical pattern
    `refs/checkpoints/sgc-test-task/agent-test-NNNN` (4-digit zero-padded N).
  - The ref resolves to a valid git SHA whose tree is non-empty (the modified
    file content is captured).
  - One JSONL line is appended to
    `metrics/<session>/shadow-checkpoints.jsonl` with keys
    `{ts, hook, task_id, worktree_slug, step, ref, sha, duration_ms, success}`
    and `success: true`.

## Out of Scope

- Restore / rollback workflow (capture mechanism only — no UX layer in v1).
- Wall-clock cap enforcement (deferred to v2 once `duration_ms` data is
  available).
- Cross-worktree merge of checkpoint trees.
