#!/usr/bin/env bats

setup() {
  TMPDIR_BAT=$(mktemp -d)
  export CLAUDE_CONFIG_DIR="$TMPDIR_BAT"
  mkdir -p "$CLAUDE_CONFIG_DIR/knowledge"
  unset CLAUDE_VERSION
}

teardown() { rm -rf "$TMPDIR_BAT"; }

load_helper() {
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
}

# --- AC3: _ssvc_version_lt numeric semver ordering ---

@test "_ssvc_version_lt: equal versions returns false" {
  load_helper
  run _ssvc_version_lt 2.1.160 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running patch greater returns false" {
  load_helper
  run _ssvc_version_lt 2.1.161 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running patch less returns true" {
  load_helper
  run _ssvc_version_lt 2.1.159 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: running minor greater returns false" {
  load_helper
  run _ssvc_version_lt 2.2.0 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running minor less returns true" {
  load_helper
  run _ssvc_version_lt 2.0.0 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: running major greater returns false" {
  load_helper
  run _ssvc_version_lt 3.0.0 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running major less returns true" {
  load_helper
  run _ssvc_version_lt 1.9.9 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: multi-digit patch numeric not lexical (9 < 160)" {
  load_helper
  run _ssvc_version_lt 2.1.9 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: empty string A returns false (no-warn on missing version)" {
  load_helper
  run _ssvc_version_lt "" 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short version 2.1 padded to 2.1.0 equals 2.1.0" {
  load_helper
  run _ssvc_version_lt 2.1 2.1.0
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short floor 2.1 pads patch to 0 (2.1.5 not below 2.1)" {
  load_helper
  run _ssvc_version_lt 2.1.5 2.1
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short running 2.1 pads patch to 0 (2.1 below 2.1.5)" {
  load_helper
  run _ssvc_version_lt 2.1 2.1.5
  [ "$status" -eq 0 ]
}

# --- Finding 1: regex guard pins non-empty malformed operands (silent false) ---
# Regression-pin: defends the ^[0-9]+(\.[0-9]+)*$ guard against a mutation that
# weakens it (e.g. to a start-anchor-only ^[0-9]). Asserts malformed operands on
# either side return 1 silently rather than being parsed and compared.

@test "_ssvc_version_lt: malformed A operand (2.1.x) returns false silently" {
  load_helper
  run _ssvc_version_lt 2.1.x 2.1.160
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

@test "_ssvc_version_lt: malformed B operand (abc) returns false silently" {
  load_helper
  run _ssvc_version_lt 2.1.160 abc
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

# --- Finding 2: leading-zero components compare base-10, no octal stderr noise ---

@test "_ssvc_version_lt: leading-zero component (2.1.008) compares as 8 < 160, no stderr" {
  load_helper
  run _ssvc_version_lt 2.1.008 2.1.160
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_version_lt: leading-zero component (2.1.020 vs 2.1.008) compares as 20 >= 8" {
  load_helper
  run _ssvc_version_lt 2.1.020 2.1.008
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

# --- AC1: _ssvc_check_version minimum-version semantics ---

@test "_ssvc_check_version: running equal to floor is silent" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.160"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_check_version: running above floor is silent" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.200"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_check_version: running below floor emits VERSION FLOOR warning" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.100"
  load_helper
  run _ssvc_check_version
  [[ "$output" =~ "VERSION FLOOR" ]]
}

@test "_ssvc_check_version: non-blocking exit 0 even when below floor" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="1.0.0"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
}

@test "_ssvc_check_version: no pin file is silent" {
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_check_version: pin file present but CLAUDE_VERSION unset and no claude binary is silent" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  unset CLAUDE_VERSION
  # Mask the claude binary so the fallback subshell produces empty output
  function claude() { return 1; }
  export -f claude
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- AC2: real version-pin file value ---

@test "version-pin file contains 2.1.160" {
  run cat "${BATS_TEST_DIRNAME}/../../version-pin"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^2\.1\.160$ ]]
}

# --- GP-05: v2.1. snapshot guard ---
# The allowlist at tests/shell/version-allowlist.txt captures every unique
# trimmed line in tracked .md files that contains 'v2.1.' at baseline.
# These tests ensure no new un-allowlisted v2.1. reference is added to the
# codebase without explicitly updating the allowlist.

@test "version-allowlist.txt exists and is non-empty" {
  local allowlist="${BATS_TEST_DIRNAME}/version-allowlist.txt"
  [ -f "$allowlist" ]
  [ -s "$allowlist" ]
}

@test "every tracked .md line containing v2.1. is in the allowlist" {
  local repo_root
  repo_root="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  local allowlist="${BATS_TEST_DIRNAME}/version-allowlist.txt"

  # Build current set: same pipeline used to generate the allowlist
  local current_set violations_file
  current_set="$(git -C "$repo_root" grep -hF 'v2.1.' -- '*.md' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
    | sort -u)"

  violations_file="$(mktemp)"
  while IFS= read -r trimmed; do
    # Use a temp file with the pattern to avoid grep treating leading dashes as flags
    local pat_file
    pat_file="$(mktemp)"
    printf '%s\n' "$trimmed" > "$pat_file"
    if ! grep -qxFf "$pat_file" "$allowlist"; then
      printf '%s\n' "$trimmed" >> "$violations_file"
    fi
    rm -f "$pat_file"
  done <<< "$current_set"

  if [ -s "$violations_file" ]; then
    echo "FAIL: the following v2.1. lines are not in tests/shell/version-allowlist.txt:"
    while IFS= read -r v; do
      echo "  >> $v"
    done < "$violations_file"
    rm -f "$violations_file"
    return 1
  fi
  rm -f "$violations_file"
}
