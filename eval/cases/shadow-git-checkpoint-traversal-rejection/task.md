# shadow-git-checkpoint — path-traversal rejection

## Problem

Per F6 (path-traversal via bash variables — OWASP A01, 2 prior HIGH findings)
and the 3/3 harness rework rate, ANY external string used in a path or git ref
name MUST be sanitized against `^[A-Za-z0-9_.-]+$` before construction. The
`refs/checkpoints/{task-id}/{slug}-{step}` namespace is a git ref namespace —
`..`, `/`, or whitespace in either the task-id or the worktree-slug component
would let an edit traverse to arbitrary refs (including
`refs/heads/main`).

This case verifies the **traversal-rejection path**: when the file path
resolves to a worktree whose basename is hostile (`agent-..`), the hook
produces NO ref anywhere in the global checkpoint namespace.

## Acceptance Criteria

- A "worktree" exists at `<TMP>/.claude/worktrees/agent-..` (basename is
  literally `agent-..`).
- An active pipeline state file exists at
  `<TMP>/.claude/pipeline-state/sgc-test-task/pipeline.md` declaring
  `task_id: sgc-test-task`, `verdict: in_progress`.
- A real reference worktree (also under `.claude/worktrees/agent-test/`) exists
  for ref-namespace observation.
- Firing the hook with `tool_input.file_path` pointing inside the hostile
  worktree:
  - The hook exits 0 (PostToolUse must NEVER block the originating tool call).
  - ZERO refs are created under `refs/checkpoints/` anywhere in the ref
    database — verified by `git for-each-ref refs/checkpoints/` returning empty.
  - No ref ends up under `refs/heads/main` or any other namespace as a
    side-effect.
- The same hostile-input rejection applies if the task-id resolver yields a
  hostile string (e.g., a corrupt pipeline state file with
  `task_id: ../../../etc/passwd`): the validator rejects it before ref
  construction.

## Out of Scope

- Hostile values inside the file content (the file content is captured into a
  stash blob; sandboxing the content is git's job, not the hook's).
- Hostile environment variables outside the validator's scope (the hook reads
  only `tool_input.file_path` from stdin and a small whitelist of env vars,
  each handled defensively).
