---
category: discovery
---

Hook source path resolution discovery: every hook in `hooks/*.sh` sources its
log helper via `source ~/.claude/hooks/_lib/log.sh` — the literal `~/.claude`
prefix expands to `$HOME/.claude` (REPO_ROOT), NOT to the worktree directory
(`$HOME/.claude/.claude/worktrees/agent-XXXX`). Tests run from the worktree
that invoke a worktree hook will source REPO_ROOT's `_lib/log.sh` (the OLD
unmodified version), so changes to `worktree/hooks/_lib/log.sh` do NOT take
effect during the test run — only after PR merge to main.

The plan assumed the +2-line `subagent_type` parse+pass would be testable
from the worktree against the worktree's modified `log.sh`. It is not, until
either (a) the file is symlinked, (b) the source path is changed.

Resolution applied: switch the 6 Agent-relevant hooks (and `runtime-guard.sh`
which also needs the new `runtime-guard-respawn.sh` helper) from
`source ~/.claude/hooks/_lib/log.sh` to `source "${HOOK_DIR}/_lib/log.sh"`,
with `HOOK_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` computed FIRST
(before `_log_hook_start`). Other hooks (the 36 non-Agent hooks) are
unchanged — they continue to call `log_hook_event $?` (1 arg) and the new
`_lib/log.sh` (when merged) treats the 2nd arg as empty (default), emitting
no `subagent_type` field. Backward compatibility holds.

Side benefit: the BASH_SOURCE-relative pattern is more robust generally —
the hook works correctly when invoked from any path, including symlinks,
without depending on `$HOME` resolving to the right tree.

Cost: ~2 lines reordered per modified hook (HOOK_DIR up; source path changed
from `~/...` to `${HOOK_DIR}/...`). No new files. No widening of scope.
