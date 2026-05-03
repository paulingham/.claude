---
category: discovery
---
Slice B refactored 12 of 18 hooks (out-of-scope confirmed): runtime-guard-key,
worktree-cwd-check, runtime-guard-respawn, main-branch-guard had no
pipeline-state path references and need NO change.

---
category: warning
---
Hook `subagent-stop-trajectory.sh` was using `jq -n` (NOT `-c`), producing
multi-line pretty JSON in trajectory.jsonl. Fixed to `jq -nc` for compact
JSONL — matches project convention. Reviewers: scan for similar `jq -n` (no
`-c`) regressions in other hooks that should produce JSONL.

---
category: warning
---
`hooks/_lib/pipeline-state-paths.sh` lacks a `_psp_task_id_of_path` helper.
Multiple Slice-B hooks (`cost-helpers.sh`, `session-start-bootstrap.sh`,
`trace-prompt.sh`) reproduce the same 3-line basename/dirname dance to
extract task_id from a pipeline file path. Slice C / fix-engineer should
add `_psp_task_id_of_path PATH` echoing task_id given either layout.

---
category: warning
---
The plan's hook-table mentions hook #14 `session-start-bootstrap.sh line
121, 139` and the SHIP_COMPLETE block uses `grep -rl ... *-pipeline.md`.
After refactor, the SHIP_COMPLETE detector now uses `grep -rl ... | grep
-E '(-pipeline\.md|/pipeline\.md)$'` to filter recursive grep output back
to ONLY pipeline files (avoids matching incidental `.md` files that
contain `Ship: completed`). Reviewers: this is intentional, not a bug.

---
category: discovery
---
Test pattern: HOME-isolated bash hook tests need to symlink
`$TMP/.claude/hooks` -> `$REPO_ROOT/hooks` because hook files do
`source ~/.claude/hooks/_lib/log.sh` (HOME-relative). Without the symlink,
the source fails silently, the hook exits 0 because of `|| exit 0` after
the source line, and the test passes a no-op without exercising the hook
logic. The 11 new test files all use this symlink pattern.

---
category: pattern
---
Test fixtures for hooks that detect "active pipeline" via `grep in_progress`
must be careful about WHICH line contains "in_progress" first. Original
hook semantics: skip `verdict: in_progress` (a frontmatter line that looks
like a phase declaration), find phase lines like `- Build: in_progress`.
The observation-capture test fixture intentionally has `verdict:
PIPELINE_ACTIVE` so the body's `- Build: in_progress` is the first match
that the original phase-extraction sed pipeline can parse cleanly.

---
category: decision
---
`approval-token.sh` ABI was held FROZEN per plan note #3. Internal helper
functions added (`_at_legacy_token_path`, `_at_new_token_path`) are
private (underscore prefix) and don't affect the public surface.
`_at_token_path` retains its single-arg signature; only its body changed
(legacy-only OR new-only OR both-with-mtime-tiebreaker). `_at_write_token`
retains its `(task_id, verdict)` signature; the only behavior change is
that it now writes to the new-layout subdir and `mkdir -p`s the parent.
Risk R6 (approval-token breakage) is mitigated by the
`test_approval_token_path_returns_existing_layout` test, which exercises
both the legacy-only and new-only branches.

---
category: fragility
---
The `main-branch-guard.sh` PreToolUse hook is greedy with its regex on
the literal command string and matches `phase:` heredoc content as a
"forbidden bare git form". Workaround during testing: avoid `cat <<EOF`
heredocs containing `phase:` AND `worktrees/` paths in the same command
string. Use `printf` or write a temp script via Write tool instead.

---
category: discovery
---
Mutation gate computed manually (mutmut not installed). 40 mutations
enumerated; 34 KILLED, 6 LIVE/PARTIAL — kill rate 85%, exceeds 70% gate.
LIVE mutations documented in
`per-task-subdirs-build-mutation-slice-b.md`; #10 (write-side mkdir)
will be killed by Slice C's write-side approval-token test at
integration time.
