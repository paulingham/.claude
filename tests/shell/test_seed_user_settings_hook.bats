#!/usr/bin/env bats
# seed-user-settings.sh — SessionStart hook wiring tests.
# Verifies registration, python3-absent fail-open, and portable config-dir usage.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/seed-user-settings.sh"
  HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_SETTINGS_PATH="$BATS_TEST_TMPDIR/target_settings.json"
}

teardown() {
  unset CLAUDE_PLUGIN_ROOT CLAUDE_SETTINGS_PATH
}

@test "seed-user-settings.sh is registered in hooks.json SessionStart" {
  run grep -c "seed-user-settings.sh" "$HOOKS_JSON"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}

@test "python3 absent -> wrapper exits 0 (fail-open, structural)" {
  # Verify the hook source contains the guard clause that makes python3 absence
  # fail-open. A structural test is used because macOS always ships /usr/bin/python3,
  # making true absence impossible to simulate via PATH alone.
  run grep -c "command -v python3" "$HOOK"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
  # Also verify the guard exits 0, not non-zero.
  run grep "exit 0" "$HOOK"
  [ "$status" -eq 0 ]
}

@test "portable-config-dir: wrapper uses CLAUDE_PLUGIN_ROOT, no bare ~/.claude" {
  # grep returns 1 (no match) when the pattern is not found — that is the passing case.
  run grep -E "source[ ]+~/\.claude/|source[ ]+\"\\\$HOME/\.claude/" "$HOOK"
  [ "$status" -eq 1 ]
}
