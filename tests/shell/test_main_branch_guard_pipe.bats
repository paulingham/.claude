#!/usr/bin/env bats
# Gap 5 — main-branch-guard.sh must NOT block allowed git commands piped to
# output filters (tail/head/grep/jq/awk/sed/cat/tr/wc/sort). Before the fix
# `git pull origin main 2>&1 | tail -5` was rejected because split_clauses
# treats `|` as a clause separator AND the first clause picks up trailing
# context that confuses the pull/fetch carve-outs.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_STATE_DIR="$TMP_HOME/.claude/state"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-mbg-pipe-$$"
  unset CLAUDE_PIPELINE_TASK_ID
  mkdir -p "$CLAUDE_STATE_DIR"
}

teardown() {
  rm -rf "$TMP_HOME"
  unset CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID HOME CLAUDE_STATE_DIR
}

_run_guard() {
  local cmd="$1"
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
    "$(printf '%s' "$cmd" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/main-branch-guard.sh" 2>&1
}

# ---------------------------------------------------------------------------
# Allowed: pipes to output filters when the leading clause is allowed
# ---------------------------------------------------------------------------

@test "git pull origin main 2>&1 | tail -5 allowed" {
  run _run_guard 'git pull origin main 2>&1 | tail -5'
  [ "$status" -eq 0 ]
}

@test "git status | head -20 allowed" {
  run _run_guard 'git status | head -20'
  [ "$status" -eq 0 ]
}

@test "git log --oneline -10 | grep feat allowed" {
  run _run_guard 'git log --oneline -10 | grep feat'
  [ "$status" -eq 0 ]
}

@test "git fetch origin | jq . allowed (degenerate but legal)" {
  # fetch with no refspec is allowed; piping to jq must not flip the verdict.
  run _run_guard 'git fetch origin | jq .'
  [ "$status" -eq 0 ]
}

@test "git diff --stat | awk NF allowed" {
  run _run_guard 'git diff --stat | awk NF'
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Still blocked: forbidden command in the LEADING clause of a pipe
# ---------------------------------------------------------------------------

@test "git checkout foo | tail still blocked (leading clause forbidden)" {
  run _run_guard 'git checkout foo | tail'
  [ "$status" -eq 2 ]
}

@test "git merge feat/x | head still blocked" {
  run _run_guard 'git merge feat/x | head'
  [ "$status" -eq 2 ]
}

@test "git reset --hard origin/main | grep . still blocked" {
  run _run_guard 'git reset --hard origin/main | grep .'
  [ "$status" -eq 2 ]
}
