#!/usr/bin/env bats
# M4: check-cc-version.sh must guard against malformed `claude --version`
# output. When the version token is not ^[0-9]+\.[0-9]+\.[0-9]+$, the script
# must exit 0 silently (still advisory; never error).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/hooks/_lib/check-cc-version.sh"
  STUB_DIR="$BATS_FILE_TMPDIR/stub-$BATS_TEST_NUMBER"
  mkdir -p "$STUB_DIR"
}

_install_claude_stub() {
  cat > "$STUB_DIR/claude" <<EOF
#!/bin/sh
printf '%s\n' '$1'
EOF
  chmod +x "$STUB_DIR/claude"
}

@test "M4: malformed version output (no version) exits 0 silently" {
  _install_claude_stub "weird-output-no-numbers"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "M4: malformed version output (only major) exits 0 silently" {
  _install_claude_stub "claude 2"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "M4: malformed version output (major.minor only) exits 0 silently" {
  _install_claude_stub "claude 2.1"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "M4: well-formed version above min exits 0 silently" {
  _install_claude_stub "claude 2.1.200"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "M4: well-formed version below min emits warning" {
  _install_claude_stub "claude 2.1.100"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"warning"* ]] || [[ "$stderr" == *"warning"* ]]
}

@test "M4: version with garbage suffix is rejected (not parsed leniently)" {
  _install_claude_stub "claude 2.1.118abc"
  PATH="$STUB_DIR:$PATH" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
