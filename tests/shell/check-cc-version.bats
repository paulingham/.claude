#!/usr/bin/env bats
# check-cc-version.sh — non-blocking warning when claude < 2.1.118.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/hooks/_lib/check-cc-version.sh"
  TMP="$(mktemp -d -t ccv.XXXXXX)"
  PATH="$TMP:$PATH"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_install_fake_claude() {
  cat > "$TMP/claude" <<EOF
#!/usr/bin/env bash
echo "$1"
EOF
  chmod +x "$TMP/claude"
}

@test "newer version → exit 0, no warning" {
  _install_fake_claude "claude 2.1.200"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "exact min version 2.1.118 → exit 0, no warning" {
  _install_fake_claude "claude 2.1.118"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "older version → exit 0, warning on stderr" {
  _install_fake_claude "claude 2.1.117"
  run "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"warning"* ]] || [[ "$output" == *"WARN"* ]] || [[ "$stderr" == *"warning"* ]]
}

@test "claude binary missing → exit 0 (non-blocking)" {
  PATH="/usr/bin:/bin"  # no claude here
  run env PATH="/usr/bin:/bin" "$SCRIPT"
  [ "$status" -eq 0 ]
}
