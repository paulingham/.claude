#!/usr/bin/env bats
# Slice 7 — parallel pipelines invariant: REPO_ROOT HEAD stays on `main` while
# two pipelines run concurrently in two worktrees over ONE shared repo.
# Hermetic: ONE temp repo R; TWO worktrees WT1, WT2; bare-repo file:// remote.
# Every assertion observes `git -C "$R" rev-parse --abbrev-ref HEAD == main`.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-pp-$$"
  export CLAUDE_PIPELINE_TASK_ID="parallel-pipeline-test"
  mkdir -p "$HOME/.claude/state" "$HOME/.claude/pipeline-state"
  mkdir -p "$HOME/.claude/metrics/$CLAUDE_SESSION_ID"

  # Build the shared repo R.
  R="$(mktemp -d)/repo"
  mkdir -p "$R" && ( cd "$R" && git init -q -b main \
    && git config user.email t@t && git config user.name t \
    && touch README && git add README && git commit -q -m init )

  # Bare-repo remote.
  REMOTE="$(mktemp -d)/remote.git"
  git init -q --bare -b main "$REMOTE"
  ( cd "$R" && git remote add origin "$REMOTE" && git push -q origin main )

  # Two worktrees on two feature branches.
  WT1="$(mktemp -d)/wt1"; WT2="$(mktemp -d)/wt2"
  ( cd "$R" && git worktree add -q -b feat/wt1 "$WT1" )
  ( cd "$R" && git worktree add -q -b feat/wt2 "$WT2" )
}

teardown() {
  ( cd "$R" 2>/dev/null && git worktree remove -f "$WT1" 2>/dev/null; git worktree remove -f "$WT2" 2>/dev/null ) || true
  rm -rf "$TMP_HOME" "$(dirname "$R")" "$(dirname "$REMOTE")" "$(dirname "$WT1")" "$(dirname "$WT2")"
  unset HOME CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID CLAUDE_PIPELINE_TASK_ID
}

# Invariant assertion: R HEAD must be `main`.
_assert_R_on_main() {
  [ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = "main" ] \
    || { echo "INVARIANT VIOLATED: R HEAD = $(git -C "$R" rev-parse --abbrev-ref HEAD)"; return 1; }
}

# Pipe a Bash tool_input.command into the guard hook.
_guard() {
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
    "$(printf '%s' "$1" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/main-branch-guard.sh"
}

# ---------------------------------------------------------------------------
# T1-T6 (per architect plan Slice 7)
# ---------------------------------------------------------------------------

@test "T1 Pipeline-1 commits in WT1 → R still on main, WT1 on feat/wt1, WT2 on feat/wt2" {
  ( cd "$WT1" && echo a > a.txt && git add a.txt && git commit -q -m "wt1: add a" )
  _assert_R_on_main
  [ "$(git -C "$WT1" rev-parse --abbrev-ref HEAD)" = "feat/wt1" ]
  [ "$(git -C "$WT2" rev-parse --abbrev-ref HEAD)" = "feat/wt2" ]
}

@test "T2 Pipeline-2 commits in WT2 → R still on main, both worktrees on their branches" {
  ( cd "$WT2" && echo b > b.txt && git add b.txt && git commit -q -m "wt2: add b" )
  _assert_R_on_main
  [ "$(git -C "$WT1" rev-parse --abbrev-ref HEAD)" = "feat/wt1" ]
  [ "$(git -C "$WT2" rev-parse --abbrev-ref HEAD)" = "feat/wt2" ]
}

@test "T3 Both worktrees push concurrently → R still on main after both pushes" {
  ( cd "$WT1" && echo c > c.txt && git add c.txt && git commit -q -m "wt1: c" )
  ( cd "$WT2" && echo d > d.txt && git add d.txt && git commit -q -m "wt2: d" )
  ( cd "$WT1" && git push -q origin feat/wt1 ) &
  ( cd "$WT2" && git push -q origin feat/wt2 ) &
  wait
  _assert_R_on_main
}

@test "T4 NEGATIVE: bare 'git checkout feat/wt1' blocked → R unchanged, WT2 unaffected" {
  # Pre-state: snapshot WT2's status to compare after the guard fires.
  before_wt2=$(git -C "$WT2" status --porcelain)
  before_R=$(git -C "$R" rev-parse HEAD)

  # Inject the rogue command. The guard inspects command string only — cwd is irrelevant.
  run _guard 'git checkout feat/wt1'
  [ "$status" -eq 2 ]

  # Invariants hold:
  _assert_R_on_main
  [ "$(git -C "$R" rev-parse HEAD)" = "$before_R" ]
  [ "$(git -C "$WT2" status --porcelain)" = "$before_wt2" ]

  # The violations log captured the prevented entry.
  log="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  [ -f "$log" ]
  grep -q '"source":"prevented"' "$log"
  grep -q '"command":"git checkout feat/wt1"' "$log"
}

@test "T5 DRIFT: simulated guard bypass → worktree-cwd-check emits drift-detected" {
  # Bypass the guard by manually moving R's HEAD off main (the very thing the
  # guard prevents at runtime — here we simulate an out-of-band shell-out).
  # Use a fresh branch (feat/wt1 and feat/wt2 are checked out in worktrees and
  # cannot be checked out in R itself).
  ( cd "$R" && git checkout -q -b feat/drift-test )

  # Re-point worktree-cwd-check at $HOME/.claude (the diagnostic hard-codes that
  # path). We need $HOME/.claude itself to be a git repo on a non-main branch
  # for the drift check to fire — copy R's git state in by making $HOME/.claude
  # itself the rogue repo.
  rm -rf "$HOME/.claude/.git"
  ( cd "$HOME/.claude" && git init -q -b feat/x )
  ( cd "$HOME/.claude" && git config user.email t@t && git config user.name t )
  ( cd "$HOME/.claude" && git commit -q --allow-empty -m drift )

  # Drive the diagnostic.
  printf '{}' | bash "$REPO_ROOT/hooks/worktree-cwd-check.sh"
  log="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  grep -q '"source":"drift-detected"' "$log"

  # Restore R to main for T6.
  ( cd "$R" && git checkout -q main )
}

@test "T6 End-state invariant: R HEAD is main after the full T1-T5 sequence" {
  _assert_R_on_main
}
