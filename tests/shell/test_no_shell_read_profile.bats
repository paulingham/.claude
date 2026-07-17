#!/usr/bin/env bats
# Phase B WS1.3 — no-shell-read.sh must respect CLAUDE_HOOK_PROFILE so it
# stops blocking cat/head/tail in the PAIR (minimal) gear, while remaining
# active for the standard (default) profile. Hermetic: run from within a
# temp git repo fixture, since the hook resolves REPO_ROOT via `pwd`.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"

  # Fixture git repo so REPO_ROOT resolution (git rev-parse from pwd) succeeds
  # and a real in-repo file path exists to target with cat/head/tail.
  # `cd -P` canonicalizes symlinks (macOS /tmp -> /private/tmp) so this path
  # string-matches what `git rev-parse --show-toplevel` returns inside the hook —
  # otherwise the /tmp-vs-/private/tmp alias makes nsr_path_in_repo's string
  # comparison spuriously fail-open on macOS.
  TMP_REPO="$(cd -P "$(mktemp -d)" && pwd)"
  ( cd "$TMP_REPO" && git init -q -b main )
  ( cd "$TMP_REPO" && git config user.email t@t && git config user.name t )
  printf 'hello\n' > "$TMP_REPO/foo.txt"
  ( cd "$TMP_REPO" && git add foo.txt && git commit -q -m init )
}

teardown() {
  rm -rf "$TMP_HOME" "$TMP_REPO"
  unset CLAUDE_HOOK_PROFILE HOME CLAUDE_PLUGIN_ROOT
}

_run_guard() {
  local cmd="$1"
  ( cd "$TMP_REPO" && printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
      "$(printf '%s' "$cmd" | jq -Rs .)" \
      | bash "$REPO_ROOT/hooks/no-shell-read.sh" )
}

@test "CLAUDE_HOOK_PROFILE=minimal: cat on a repo file is allowed (exit 0)" {
  export CLAUDE_HOOK_PROFILE="minimal"
  run _run_guard 'cat foo.txt'
  [ "$status" -eq 0 ]
}

@test "CLAUDE_HOOK_PROFILE=standard (default): cat on a repo file is still blocked (exit 2)" {
  export CLAUDE_HOOK_PROFILE="standard"
  run _run_guard 'cat foo.txt'
  [ "$status" -eq 2 ]
}

@test "unset CLAUDE_HOOK_PROFILE (default=standard): cat on a repo file is still blocked (exit 2)" {
  unset CLAUDE_HOOK_PROFILE
  run _run_guard 'cat foo.txt'
  [ "$status" -eq 2 ]
}
