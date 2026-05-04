#!/usr/bin/env bats

setup() {
  TMPDIR_BAT=$(mktemp -d)
  export HOME="$TMPDIR_BAT"
  export CLAUDE_SESSION_ID="test-$$"
  export CLAUDE_CONFIG_DIR="$TMPDIR_BAT/.claude-config"
  mkdir -p "$CLAUDE_CONFIG_DIR/hooks/_lib" "$HOME/.claude/metrics/test-$$"
  cat > "$CLAUDE_CONFIG_DIR/hooks/_lib/log.sh" <<EOF
_log_hook_start() { :; }
_log_hook_trigger() { :; }
log_hook_event() { :; }
EOF
}

teardown() { rm -rf "$TMPDIR_BAT"; }

@test "self-test produces hook-health.jsonl" {
  cat > "$CLAUDE_CONFIG_DIR/hooks/dummy-safe.sh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$CLAUDE_CONFIG_DIR/hooks/dummy-safe.sh"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/hook-self-test.sh"
  [ "$status" -eq 0 ]
  [ -f "$HOME/.claude/metrics/test-$$/hook-health.jsonl" ]
}

@test "self-test respects skip annotation" {
  cat > "$CLAUDE_CONFIG_DIR/hooks/dummy-skip.sh" <<'EOF'
#!/usr/bin/env bash
# self-test: skip
exit 99
EOF
  chmod +x "$CLAUDE_CONFIG_DIR/hooks/dummy-skip.sh"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/hook-self-test.sh"
  [ "$status" -eq 0 ]
  grep -q '"hook": "dummy-skip.sh".*"mode": "registration"' "$HOME/.claude/metrics/test-$$/hook-health.jsonl"
}

@test "self-test exits zero on assertion failure" {
  cat > "$CLAUDE_CONFIG_DIR/hooks/dummy-broken.sh" <<'EOF'
#!/usr/bin/env bash
syntax error here
EOF
  chmod -x "$CLAUDE_CONFIG_DIR/hooks/dummy-broken.sh"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/hook-self-test.sh"
  [ "$status" -eq 0 ]
}

@test "self-test fast-exit payload is Read tool" {
  grep -q "Read" "${BATS_TEST_DIRNAME}/../../hooks/hook-self-test.sh"
}

@test "self-test does not run real test commands" {
  ! grep -E "npm test|bundle exec rspec|pytest --" "${BATS_TEST_DIRNAME}/../../hooks/hook-self-test.sh"
}
