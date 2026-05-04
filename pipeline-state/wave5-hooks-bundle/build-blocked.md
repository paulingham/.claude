# Wave 5 Hooks Bundle — Build Blocked

**Status**: HALTED before BATCHED RED step.
**Reason**: orchestrator-discipline.sh PreToolUse hook blocks ALL Write/Edit operations from this build agent because the harness is not injecting `subagent_type` and the path-allowlist does not recognize `.claude-sessions/` as a valid agent worktree path.

## Reproduction

Every attempt to Write/Edit a non-`.md` file inside the worktree at `.claude-sessions/wave5-hooks-bundle-main/` is rejected with:

```
PreToolUse:Write hook error: BLOCKED: Orchestrator cannot write source files directly.
Delegate to an agent via the appropriate skill.
```

This includes `.py` test files, `.bats` test files, `.sh` hooks (which are required deliverables of this bundle), and edits to existing source.

## Root cause

`hooks/orchestrator-discipline.sh::is_path_allow_listed`:

```bash
is_path_allow_listed() {
    [[ -z "$1" || "$1" =~ \.md$ ]] && return 0
    [[ "$1" =~ \.claude/automation/ || "$1" =~ \.claude/hooks/ ]] && return 0
    # ...
    [[ "$1" =~ /\.claude/worktrees/ ]]
}
```

- `.claude/hooks/` is the LITERAL substring; my worktree-path is `.claude-sessions/wave5-hooks-bundle-main/hooks/`, which does NOT match.
- `\.claude/worktrees/` is the LITERAL substring; my worktree path uses `.claude-sessions/<name>-main/`, which does NOT match.
- Subagent detection (`is_caller_a_subagent`) reads `subagent_type` from PreToolUse stdin JSON. The harness is not injecting it for this Team-spawned build agent, so the fallback fails.

## What unblocks the build

ANY ONE of:

1. **Update the orchestrator-discipline path allowlist** to recognize `/.claude-sessions/`:
   ```bash
   [[ "$1" =~ /\.claude/worktrees/ ]] && return 0
   [[ "$1" =~ /\.claude-sessions/ ]]   # NEW — match web-session-bootstrap layout
   ```
   This is a one-line change but I cannot make it because the hook path itself is blocked by the same hook.

2. **Harness fix**: ensure `subagent_type` is injected into PreToolUse stdin JSON for Team-dispatched build agents. This is already documented as the primary detection path; the secondary CWD fallback was added explicitly to mitigate harness gaps but does not cover `.claude-sessions/`.

3. **Operator override**: set `CLAUDE_HOOK_PROFILE=disabled` for the build agent's session, or add `CLAUDE_DISABLE_ORCHESTRATOR_DISCIPLINE=1` and have the hook fast-exit on it.

## What I have completed

- Read the plan at `pipeline-state/wave5-hooks-bundle/plan.md` (41 test stubs across 7 ACs).
- Read all current state of `hooks/quality-gate.sh` (259 lines), `hooks/tdd-guard.sh` (33 lines), `hooks/session-start-bootstrap.sh` (211 lines), `hooks/_lib/worktree-cwd-pairing.sh` (22 lines), `hooks/worktree-cwd-check.sh` (43 lines), `hooks/orchestrator-discipline.sh` (full).
- Read existing test conventions (BATS shape from `tests/shell/test_destructive_verb_block.bats`, Python shape from `tests/test_code_shape_defaults.bats`).
- Confirmed the canonical pairing pattern in `hooks/_lib/worktree-cwd-pairing.sh` is the one to mirror per plan §4.

I have a complete mental model of the BATCHED RED → IMPLEMENT → REFACTOR → MUTATION cycle for all 7 slices. I cannot execute it without write access.

## Verdict

**BUILD_FAILED** — environment blocker. Not a code problem; the build cannot start until the orchestrator-discipline path-allowlist or harness `subagent_type` injection is fixed.
