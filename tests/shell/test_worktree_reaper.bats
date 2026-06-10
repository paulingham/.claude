#!/usr/bin/env bats
# worktree-reaper.sh — SAFE git-worktree reaper for SessionStart.
# Fully hermetic: each test owns a real temp git repo with real worktrees under
# .claude/worktrees/. HARNESS_ROOT/CLAUDE_PLUGIN_ROOT point at the real repo so
# the hook + _lib resolve; HARNESS_DATA points at a temp dir so no live state is
# touched. CLAUDE_WORKTREE_REAPER_INTERVAL_HOURS=0 disables rate-limiting.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/worktree-reaper.sh"

  WORK="$BATS_TEST_TMPDIR/work"
  mkdir -p "$WORK"
  export HARNESS_DATA_DIR="$BATS_TEST_TMPDIR/harness-data"
  mkdir -p "$HARNESS_DATA_DIR/metrics"

  # Resolve the hook + _lib against the real repo; runtime state at temp.
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$HARNESS_DATA_DIR"
  export CLAUDE_WORKTREE_REAPER_INTERVAL_HOURS=0

  # Build the main repo with a committed main branch.
  MAIN="$WORK/repo"
  mkdir -p "$MAIN"
  git -C "$MAIN" init -q -b main
  git -C "$MAIN" config user.email t@t
  git -C "$MAIN" config user.name t
  printf 'seed\n' > "$MAIN/README.md"
  git -C "$MAIN" add README.md
  git -C "$MAIN" commit -q -m "init"
  mkdir -p "$MAIN/.claude/worktrees"
}

teardown() {
  unset CLAUDE_PLUGIN_ROOT CLAUDE_PLUGIN_DATA CLAUDE_WORKTREE_REAPER_INTERVAL_HOURS
}

# Run the reaper from inside the main repo (SessionStart cwd is the repo root).
_run_reaper() {
  ( cd "$MAIN" && bash "$HOOK" )
}

# Create a worktree at .claude/worktrees/<name> on a new branch <name>.
# Leaves it clean + merged + 0-ahead unless the caller mutates it after.
_make_worktree() {
  local name="$1"
  git -C "$MAIN" worktree add -q -b "$name" ".claude/worktrees/$name" main
}

# Merge a worktree's branch back into main (no new commits → fast-forward noop,
# but the branch is still listed by `branch --merged main`).
_merge_branch() {
  git -C "$MAIN" merge -q --no-ff "$1" -m "merge $1" 2>/dev/null || true
}

# ---------------------------------------------------------------------------

@test "AC1 merged + clean + 0-ahead worktree IS removed" {
  _make_worktree safe
  run _run_reaper
  [ "$status" -eq 0 ]
  [ ! -d "$MAIN/.claude/worktrees/safe" ]
  echo "$output" | grep -q "reaped"
  echo "$output" | grep -qE "reaped [1-9]"
}

@test "AC2 merged + 0-ahead but UNTRACKED file → NOT removed (the trap)" {
  _make_worktree trap
  printf 'orphan work\n' > "$MAIN/.claude/worktrees/trap/new-untracked.txt"
  run _run_reaper
  [ "$status" -eq 0 ]
  [ -d "$MAIN/.claude/worktrees/trap" ]
  [ -f "$MAIN/.claude/worktrees/trap/new-untracked.txt" ]
  echo "$output" | grep -q "trap"
}

@test "AC3 unmerged branch with a commit ahead of main → NOT removed" {
  _make_worktree ahead
  printf 'ahead\n' > "$MAIN/.claude/worktrees/ahead/feature.txt"
  git -C "$MAIN/.claude/worktrees/ahead" add feature.txt
  git -C "$MAIN/.claude/worktrees/ahead" commit -q -m "ahead commit"
  run _run_reaper
  [ "$status" -eq 0 ]
  [ -d "$MAIN/.claude/worktrees/ahead" ]
  echo "$output" | grep -q "ahead"
}

@test "AC4 clean-but-MODIFIED tracked file (uncommitted) → NOT removed" {
  _make_worktree dirty
  printf 'modified\n' >> "$MAIN/.claude/worktrees/dirty/README.md"
  run _run_reaper
  [ "$status" -eq 0 ]
  [ -d "$MAIN/.claude/worktrees/dirty" ]
}

@test "AC5 CLAUDE_DISABLE_WORKTREE_REAPER=1 → fast exit 0, removes nothing" {
  _make_worktree safe
  CLAUDE_DISABLE_WORKTREE_REAPER=1 run _run_reaper
  [ "$status" -eq 0 ]
  [ -d "$MAIN/.claude/worktrees/safe" ]
}

@test "AC6 non-git cwd (no .claude/worktrees) → exit 0, no error" {
  NONGIT="$BATS_TEST_TMPDIR/nongit"
  mkdir -p "$NONGIT"
  # GIT_CEILING_DIRECTORIES stops git's upward walk at $BATS_TEST_TMPDIR so
  # the hook's `git rev-parse --git-dir` fails even when $BATS_TEST_TMPDIR is
  # nested inside a git repo (e.g. the GitHub Actions checkout).
  run bash -c "cd '$NONGIT' && GIT_CEILING_DIRECTORIES='$BATS_TEST_TMPDIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC7 size cap exceeded → prominent warning on stderr" {
  _make_worktree safe
  CLAUDE_WORKTREE_SIZE_CAP_MB=0 run _run_reaper
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "size"
}
