# Session Isolation Patterns

How the harness shares engineering state (session memory, learning loop, manifests, memory.sqlite) across session worktrees of `$HOME/.claude` while keeping per-branch state isolated. Cross-referenced from `rules/agent-protocol.md` and `rules/autonomous-intelligence.md`.

## Worktree model

Every concurrent session of the harness runs in its own git worktree under
`${CLAUDE_SESSIONS_ROOT:-$HOME/.claude-sessions}/<repo-slug>/<name>`, created
by `scripts/new-session.sh`. Each worktree holds an independent branch and
independent `pipeline-state/` — so two sessions can drive different pipelines
in parallel without stepping on each other.

But some state MUST travel with the user, not the branch: session memory, the
learning loop's observations, the project manifest, the long-lived memory
sqlite. Those are user-level engineering context; branching them per worktree
would silently degrade the autonomous-intelligence loop.

## Per-branch vs shared state

When `--repo` resolves to the canonical `$HOME/.claude`, `new-session.sh`
symlinks the shared paths from the worktree into the real harness. Non-harness
repos are never touched by state sharing.

| Path                       | Mode       | Why                                           |
|----------------------------|------------|-----------------------------------------------|
| `session-memory/`          | shared     | Engineering notes must follow the user        |
| `learning/`                | shared     | Observations + instincts are global knowledge |
| `manifests/`               | shared     | Project manifest is user-level config         |
| `db/memory.sqlite`         | shared     | Long-lived memory store follows the user      |
| `pipeline-state/`          | per-branch | Each session drives its own pipeline          |
| `agent-memory/`            | per-branch | Tracked in git; changes ride with branch      |
| `db/schema.sql`            | per-branch | Schema version belongs to the branch's code   |

Slice 5c wires this in `scripts/_lib/state-symlink.sh`; the helper is
idempotent (`ln -sfn`) and bootstraps missing targets with `mkdir -p` /
`touch` so first-run sessions succeed even on a fresh harness checkout.

## Safety considerations

`memory.sqlite` is opened with WAL journaling, so two sessions writing through
the shared symlink concurrently is safe at the SQLite layer — readers never
block writers and a single writer is serialised. The surrounding embedder
already uses short transactions and a connection-pool per process, so the
shared file is not a bottleneck in practice. Cross-process corruption would
require a non-WAL journal mode or a network filesystem, neither of which the
harness uses.

Dangling symlinks are reported by `_verify_symlinks` on stderr after apply —
useful signal if `$HOME/.claude/session-memory` is deleted out from under
running sessions.

## When to use --no-state-share

Pass `--no-state-share` to `new-session.sh` when:

- Reproducing a bug that may be caused by corrupt session memory (isolate the
  session from the shared store).
- Running a throwaway experiment that should not pollute the learning loop.
- Testing the harness itself — bats specs set `$HOME` to a tempdir so the real
  state is never touched, but manual exploratory runs can use the flag for
  the same guarantee.

Without the flag, a harness-of-harness session automatically shares state.

## Rollback impact

After reverting Slice 5c, new session worktrees of `$HOME/.claude` start with empty `session-memory/`, `learning/`, `manifests/` — the autonomous-intelligence loop silently degrades.

Mitigation (manual, from inside a session worktree):

```
for d in session-memory learning manifests; do ln -sfn "$HOME/.claude/$d" "$(git rev-parse --show-toplevel)/$d"; done && ln -sfn "$HOME/.claude/db/memory.sqlite" "$(git rev-parse --show-toplevel)/db/memory.sqlite"
```

Run once per session worktree to restore sharing. Re-applying Slice 5c is preferred.
