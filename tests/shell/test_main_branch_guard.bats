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
}

teardown() {
  rm -rf "$TMP_HOME"
  unset CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID HOME CLAUDE_STATE_DIR
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

@test "AC2.2 git -C /tmp/wt checkout foo allowed" {
  run _run_guard Bash 'git -C /tmp/wt checkout foo'
  [ "$status" -eq 0 ]
}

@test "AC2.3 (cd /tmp/wt && git checkout foo) allowed" {
  run _run_guard Bash '(cd /tmp/wt && git checkout foo)'
  [ "$status" -eq 0 ]
}

@test "AC2.4 cd /tmp/wt && git checkout foo allowed" {
  run _run_guard Bash 'cd /tmp/wt && git checkout foo'
  [ "$status" -eq 0 ]
}

@test "AC2.5 gh pr create --title x blocked" {
  run _run_guard Bash 'gh pr create --title x'
  [ "$status" -eq 2 ]
}

@test "AC2.6 (cd /tmp/wt && gh pr create --title x) allowed" {
  run _run_guard Bash '(cd /tmp/wt && gh pr create --title x)'
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
