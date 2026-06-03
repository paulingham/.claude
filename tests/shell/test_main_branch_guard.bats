#!/usr/bin/env bats
# Slice 2 — main-branch-guard PreToolUse hook (22 ACs, AC2.1-AC2.22).
# Hermetic: $HOME redirected to mktemp -d; hooks/ symlinked into fake $HOME so
# `source ~/.claude/hooks/...` resolves. Profile defaults to "minimal" so the
# guard runs (it gates on minimal — same precedent as quality-gate).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  # macOS gotcha (per Engineer A scratchpad): ln -sfn does NOT replace existing
  # dir — it nests INSIDE. Force-remove target first, then symlink.
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_STATE_DIR="$TMP_HOME/.claude/state"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-mbg-$$"
  unset CLAUDE_PIPELINE_TASK_ID
  mkdir -p "$CLAUDE_STATE_DIR"
  # Hermetic registered worktree for delegation validation tests.
  TMP_REPO_MBG="$(mktemp -d)"
  ( cd "$TMP_REPO_MBG" && git init -q -b main )
  ( cd "$TMP_REPO_MBG" && git config user.email t@t && git config user.name t )
  ( cd "$TMP_REPO_MBG" && git commit -q --allow-empty -m init )
  TMP_WT="$(mktemp -d)/wt"
  ( cd "$TMP_REPO_MBG" && git worktree add -q -b feat/x "$TMP_WT" )
  export CLAUDE_WORKTREE_PATH="$TMP_WT"
}

teardown() {
  rm -rf "$TMP_HOME"
  rm -rf "$(dirname "${TMP_WT:-/tmp/__nonexistent__}")"
  rm -rf "${TMP_REPO_MBG:-}"
  unset CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID HOME CLAUDE_STATE_DIR CLAUDE_WORKTREE_PATH
}

# Helper: pipe a {tool_name, tool_input.command} JSON record into the guard.
_run_guard() {
  local tool_name="$1" command="$2"
  printf '{"tool_name":"%s","tool_input":{"command":%s}}' \
    "$tool_name" "$(printf '%s' "$command" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/main-branch-guard.sh"
}

# Helper for cases that need stderr capture.
_run_guard_capture() {
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
    "$(printf '%s' "$1" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/main-branch-guard.sh" 2>&1
}

# ---------------------------------------------------------------------------
# AC2.1-AC2.22 — one bats test per AC
# ---------------------------------------------------------------------------

@test "AC2.1 git checkout foo blocked with stderr message" {
  run _run_guard_capture 'git checkout foo'
  [ "$status" -eq 2 ]
  echo "$output" | grep -qE 'BLOCKED: REPO_ROOT HEAD must stay on .main.'
}

@test "AC2.2 git -C <registered-wt> checkout foo allowed" {
  run _run_guard Bash "git -C $TMP_WT checkout foo"
  [ "$status" -eq 0 ]
}

@test "AC2.3 (cd <registered-wt> && git checkout foo) allowed" {
  run _run_guard Bash "(cd $TMP_WT && git checkout foo)"
  [ "$status" -eq 0 ]
}

@test "AC2.4 cd <registered-wt> && git checkout foo allowed" {
  run _run_guard Bash "cd $TMP_WT && git checkout foo"
  [ "$status" -eq 0 ]
}

@test "AC2.5 gh pr create --title x blocked" {
  run _run_guard Bash 'gh pr create --title x'
  [ "$status" -eq 2 ]
}

@test "AC2.6 (cd <registered-wt> && gh pr create --title x) allowed" {
  run _run_guard Bash "(cd $TMP_WT && gh pr create --title x)"
  [ "$status" -eq 0 ]
}

@test "AC2.7 git status allowed" {
  run _run_guard Bash 'git status'
  [ "$status" -eq 0 ]
}

@test "AC2.8 git fetch origin (no refspec) allowed" {
  run _run_guard Bash 'git fetch origin'
  [ "$status" -eq 0 ]
}

@test "AC2.9 git fetch origin main:main blocked (local-ref refspec)" {
  run _run_guard Bash 'git fetch origin main:main'
  [ "$status" -eq 2 ]
}

@test "AC2.10 git fetch origin +refs/heads/*:refs/remotes/origin/* allowed" {
  run _run_guard Bash 'git fetch origin +refs/heads/*:refs/remotes/origin/*'
  [ "$status" -eq 0 ]
}

@test "AC2.11 git fetch --all allowed" {
  run _run_guard Bash 'git fetch --all'
  [ "$status" -eq 0 ]
}

@test "AC2.12 git fetch origin pull/123/head:pr-123 blocked" {
  run _run_guard Bash 'git fetch origin pull/123/head:pr-123'
  [ "$status" -eq 2 ]
}

@test "AC2.13 git push origin HEAD:main blocked" {
  run _run_guard Bash 'git push origin HEAD:main'
  [ "$status" -eq 2 ]
}

@test "AC2.14 git push origin foo:main blocked" {
  run _run_guard Bash 'git push origin foo:main'
  [ "$status" -eq 2 ]
}

@test "AC2.15 git push origin feature/foo allowed" {
  run _run_guard Bash 'git push origin feature/foo'
  [ "$status" -eq 0 ]
}

@test "AC2.16 git status && git checkout foo blocked (compound, second clause)" {
  run _run_guard Bash 'git status && git checkout foo'
  [ "$status" -eq 2 ]
}

@test "AC2.17 git checkout foo; git status blocked (compound, first clause)" {
  run _run_guard Bash 'git checkout foo; git status'
  [ "$status" -eq 2 ]
}

@test "AC2.18 git checkout foo || true blocked" {
  run _run_guard Bash 'git checkout foo || true'
  [ "$status" -eq 2 ]
}

@test "AC2.19 non-Bash tool exits 0 immediately" {
  run _run_guard Write 'git checkout foo'
  [ "$status" -eq 0 ]
  run _run_guard Edit 'git checkout foo'
  [ "$status" -eq 0 ]
  run _run_guard Agent 'git checkout foo'
  [ "$status" -eq 0 ]
}

@test "AC2.20 violation log gains a 'prevented' entry with the offending command" {
  run _run_guard Bash 'git checkout feat/x'
  [ "$status" -eq 2 ]
  log="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  [ -f "$log" ]
  last=$(tail -1 "$log")
  [ "$(echo "$last" | jq -r .source)" = "prevented" ]
  [ "$(echo "$last" | jq -r .command)" = "git checkout feat/x" ]
}

@test "AC2.21 CLAUDE_HOOK_PROFILE=minimal — guard runs (does NOT fast-exit)" {
  CLAUDE_HOOK_PROFILE=minimal run _run_guard Bash 'git checkout foo'
  [ "$status" -eq 2 ]
}

@test "AC2.22 CLAUDE_HOOK_PROFILE=standard — guard runs" {
  CLAUDE_HOOK_PROFILE=standard run _run_guard Bash 'git checkout foo'
  [ "$status" -eq 2 ]
}

# HIGH-5 (security) — CLAUDE_SESSION_ID path traversal MUST be sanitized
# before being used in the metrics path.
@test "AC2.23 CLAUDE_SESSION_ID with ../../etc cannot escape metrics dir" {
  CLAUDE_SESSION_ID="../../etc" run _run_guard Bash 'git checkout foo'
  [ "$status" -eq 2 ]
  # No file should land outside the metrics tree.
  [ ! -f "$HOME/etc/main-branch-violations.jsonl" ]
  [ ! -f "$HOME/.claude/etc/main-branch-violations.jsonl" ]
  # The sanitized path must exist under metrics/.
  found=$(find "$HOME/.claude/metrics" -name "main-branch-violations.jsonl" 2>/dev/null | wc -l | tr -d ' ')
  [ "$found" -ge 1 ]
}

# HIGH-6 (security) — URL-embedded credentials MUST be redacted before logging.
@test "AC2.24 secrets in URL credentials redacted in violation log" {
  cmd='git push https://user:supersecret@github.com/org/repo HEAD:main'
  run _run_guard Bash "$cmd"
  [ "$status" -eq 2 ]
  log="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  [ -f "$log" ]
  # The secret must NOT appear in the log.
  ! grep -q 'supersecret' "$log"
  # The redaction marker MUST appear.
  grep -q 'REDACTED' "$log"
}

# Pull carve-out — `git pull` to update main is safe; only non-main branch arg blocks.
@test "AC2.25 git pull allowed (bare)" {
  run _run_guard Bash 'git pull'
  [ "$status" -eq 0 ]
}

@test "AC2.26 git pull origin main allowed" {
  run _run_guard Bash 'git pull origin main'
  [ "$status" -eq 0 ]
}

@test "AC2.27 git pull --rebase origin main allowed" {
  run _run_guard Bash 'git pull --rebase origin main'
  [ "$status" -eq 0 ]
}

@test "AC2.28 git pull origin feature-branch blocked" {
  run _run_guard Bash 'git pull origin feature-branch'
  [ "$status" -eq 2 ]
}

# ---------------------------------------------------------------------------
# Delegation-target validation (AC2.29-AC2.36) — fix for REPO_ROOT bypass
# ---------------------------------------------------------------------------

@test "AC2.29 cd <REPO_ROOT_literal> && git checkout -b x blocked (exit 2)" {
  run _run_guard Bash "cd $TMP_REPO_MBG && git checkout -b x"
  [ "$status" -eq 2 ]
}

@test "AC2.30 git -C . checkout -b x blocked from harness root (exit 2)" {
  run _run_guard Bash 'git -C . checkout -b x'
  [ "$status" -eq 2 ]
}

@test "AC2.31 git -C \"\" checkout x blocked (empty target, exit 2)" {
  run _run_guard Bash 'git -C "" checkout x'
  [ "$status" -eq 2 ]
}

@test "AC2.32 git -C \"\$WORKTREE\" checkout foo allowed (variable-ref passthrough, exit 0)" {
  run _run_guard Bash 'git -C "$WORKTREE" checkout foo'
  [ "$status" -eq 0 ]
}

@test "AC2.33 (cd \"\$TMP_WT\" && git checkout foo) allowed via CLAUDE_WORKTREE_PATH (exit 0)" {
  run _run_guard Bash "(cd \"$TMP_WT\" && git checkout foo)"
  [ "$status" -eq 0 ]
}

@test "AC2.34 git -C \"\$TMP_WT\" checkout foo allowed via CLAUDE_WORKTREE_PATH (exit 0)" {
  run _run_guard Bash "git -C \"$TMP_WT\" checkout foo"
  [ "$status" -eq 0 ]
}

@test "AC2.35 git -C /nonexistent/unregistered checkout foo blocked (unregistered path, exit 2)" {
  local UNREGISTERED="/nonexistent/path-$(date +%s)"
  run _run_guard Bash "git -C $UNREGISTERED checkout foo"
  [ "$status" -eq 2 ]
}

@test "AC2.36 violation log entry for delegation-target bypass has expected fields" {
  run _run_guard Bash "cd $TMP_REPO_MBG && git checkout -b x"
  [ "$status" -eq 2 ]
  log="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/main-branch-violations.jsonl"
  [ -f "$log" ]
  last=$(tail -1 "$log")
  [ "$(echo "$last" | jq -r .source)" = "prevented" ]
  echo "$last" | jq -e '.timestamp' > /dev/null
  echo "$last" | jq -e '.session_id' > /dev/null
}
