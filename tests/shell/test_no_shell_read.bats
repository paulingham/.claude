#!/usr/bin/env bats
# no-shell-read.sh PreToolUse Bash hook.
# Blocks tail/head/cat used to read static files inside REPO_ROOT, forcing
# use of the Read tool. Allows streaming tail (-f/-F), outside-repo paths,
# and pipe-only clauses with no path argument.
# Hermetic: $HOME redirected to mktemp -d; hooks/ symlinked into fake $HOME.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_HOOK_PROFILE="standard"
  export CLAUDE_SESSION_ID="bats-nsr-$$"
  unset CLAUDE_DISABLE_NO_SHELL_READ
}

teardown() {
  rm -rf "$TMP_HOME"
  unset CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID HOME CLAUDE_DISABLE_NO_SHELL_READ
}

# Helper: pipe a Bash JSON record into the hook.
_run_hook() {
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
    "$(printf '%s' "$1" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/no-shell-read.sh"
}

_run_hook_capture() {
  printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
    "$(printf '%s' "$1" | jq -Rs .)" \
    | bash "$REPO_ROOT/hooks/no-shell-read.sh" 2>&1
}

@test "AC5 escape hatch CLAUDE_DISABLE_NO_SHELL_READ=1 returns 0 immediately" {
  export CLAUDE_DISABLE_NO_SHELL_READ=1
  run _run_hook "cat $REPO_ROOT/CLAUDE.md"
  [ "$status" -eq 0 ]
}

@test "AC4 pipe-only clause git log | tail -5 allowed (tail has no path)" {
  run _run_hook 'git log | tail -5'
  [ "$status" -eq 0 ]
}

@test "AC1 cat absolute repo path blocked with stderr message" {
  run _run_hook_capture "cat $REPO_ROOT/CLAUDE.md"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qE 'Use the Read tool instead of cat'
}

@test "AC1 head -20 hooks/foo.sh blocked (relative repo path)" {
  cd "$REPO_ROOT"
  run _run_hook_capture 'head -20 hooks/foo.sh'
  [ "$status" -eq 2 ]
  echo "$output" | grep -qE 'Use the Read tool instead of head'
}

@test "AC2 tail -f /var/log/system.log allowed (streaming, outside repo)" {
  run _run_hook 'tail -f /var/log/system.log'
  [ "$status" -eq 0 ]
}

@test "AC2 tail -f log/development.log allowed (streaming, in repo)" {
  cd "$REPO_ROOT"
  run _run_hook 'tail -f log/development.log'
  [ "$status" -eq 0 ]
}

@test "AC3 cat /tmp/scratch.txt allowed (outside repo)" {
  run _run_hook 'cat /tmp/scratch.txt'
  [ "$status" -eq 0 ]
}

@test "AC7 test -f foo || cat REPO/CLAUDE.md blocks the cat clause" {
  run _run_hook_capture "test -f foo || cat $REPO_ROOT/CLAUDE.md"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qE 'Use the Read tool instead of cat'
}

@test "non-Bash tool exits 0 immediately" {
  printf '{"tool_name":"Read","tool_input":{"file_path":"/tmp/x"}}' \
    | bash "$REPO_ROOT/hooks/no-shell-read.sh"
  [ "$?" -eq 0 ]
}
