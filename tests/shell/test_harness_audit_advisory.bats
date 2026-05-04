#!/usr/bin/env bats

setup() {
  TMPDIR_BAT=$(mktemp -d)
  export HOME="$TMPDIR_BAT"
  export CLAUDE_SESSION_ID="test-$$"
  export CLAUDE_CONFIG_DIR="$TMPDIR_BAT/.claude-config"
  mkdir -p "$CLAUDE_CONFIG_DIR/hooks/_lib" "$CLAUDE_CONFIG_DIR/agents"
  cat > "$CLAUDE_CONFIG_DIR/hooks/_lib/log.sh" <<EOF
_log_hook_start() { :; }
_log_hook_trigger() { :; }
log_hook_event() { :; }
EOF
}

teardown() { rm -rf "$TMPDIR_BAT"; }

@test "advisory exits zero always" {
  echo '{}' > "$CLAUDE_CONFIG_DIR/settings.json"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/harness-audit-advisory.sh"
  [ "$status" -eq 0 ]
}

@test "advisory does not invoke skill harness-audit" {
  # Skill invocation would be via Skill tool or executable shell — not a doc reference. Filter comment lines.
  ! grep -vE '^\s*#' "${BATS_TEST_DIRNAME}/../../hooks/harness-audit-advisory.sh" | grep -qE "Skill\(|skill[ /]+harness-audit|invoke.*harness-audit"
}

@test "advisory sources harness-audit-fast lib" {
  grep -q "harness-audit-fast.sh" "${BATS_TEST_DIRNAME}/../../hooks/harness-audit-advisory.sh"
}

@test "advisory skips slow checks" {
  ! grep -E "npm audit|bundle audit|pip-audit" "${BATS_TEST_DIRNAME}/../../hooks/harness-audit-advisory.sh"
}
