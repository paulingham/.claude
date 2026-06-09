#!/usr/bin/env bats
# Spec-blind black-box behavioural tests for hooks/_lib/check-bypass-gate.sh
#
# Contract under test (from AC list — NOT derived from implementation source):
#   A sourced bash helper exposes:  check_bypass_gate <ENV_VAR_NAME>
#
#   Return codes:
#     0  (bypass / allow)   — ONLY when the named env var equals exactly "1"
#     1  (do not bypass)    — for unset, empty, "0", "true", "yes", or any
#                             other value that is not exactly "1"
#
#   Side-effect contract:
#     Sourcing the file produces NO stdout, NO stderr, NO files created,
#     and NO environment mutation beyond defining the function.
#
# These tests are authored from the stated contract only.
# They import ONLY via the public worktree path — no src/lib reads.

HELPER="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)/hooks/_lib/check-bypass-gate.sh"

# ---------------------------------------------------------------------------
# AC-SIDEEFFECT-1: Sourcing produces no stdout
# ---------------------------------------------------------------------------
@test "sourcing the file produces no stdout" {
  stdout=$(bash -c "source '$HELPER'" 2>/dev/null)
  [[ -z "$stdout" ]]
}

# ---------------------------------------------------------------------------
# AC-SIDEEFFECT-2: Sourcing produces no stderr
# ---------------------------------------------------------------------------
@test "sourcing the file produces no stderr" {
  stderr=$(bash -c "source '$HELPER'" 2>&1 1>/dev/null)
  [[ -z "$stderr" ]]
}

# ---------------------------------------------------------------------------
# AC-SIDEEFFECT-3: Sourcing does not mutate pre-existing env vars
# ---------------------------------------------------------------------------
@test "sourcing does not mutate a pre-existing env variable" {
  result=$(bash -c "
    export SENTINEL_VAR=original_value
    source '$HELPER'
    echo \"\$SENTINEL_VAR\"
  ")
  [[ "$result" == "original_value" ]]
}

# ---------------------------------------------------------------------------
# AC-SIDEEFFECT-4: Sourcing does not create files in cwd
# ---------------------------------------------------------------------------
@test "sourcing does not create files in the current directory" {
  tmpdir=$(mktemp -d)
  bash -c "cd '$tmpdir' && source '$HELPER'" 2>/dev/null
  file_count=$(ls -A "$tmpdir" | wc -l | tr -d ' ')
  rm -rf "$tmpdir"
  [[ "$file_count" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-BYPASS-1: Var set to exactly "1" → return 0 (bypass allowed)
# ---------------------------------------------------------------------------
@test "returns 0 when the named env var is exactly '1'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=1
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 0 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-1: Var unset → return 1 (do not bypass)
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is unset" {
  result=$(bash -c "
    source '$HELPER'
    unset MY_GATE_VAR
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-2: Var set to empty string → return 1
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is empty string" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=''
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-3: Var set to "0" → return 1 (not bypass)
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is '0'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=0
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-4: Var set to "true" → return 1 (not bypass — only "1" is bypass)
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is 'true'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=true
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-5: Var set to "yes" → return 1
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is 'yes'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=yes
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-6: Var set to "false" → return 1
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is 'false'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=false
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-7: Var set to "2" → return 1 (boundary: close to "1" but not "1")
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is '2'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=2
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-8: Var set to " 1" (leading space) → return 1 (exact match only)
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is ' 1' (leading space)" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=' 1'
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-9: Var set to "1 " (trailing space) → return 1 (exact match only)
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is '1 ' (trailing space)" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR='1 '
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-10: Var set to "01" → return 1 (not exactly "1")
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is '01'" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=01
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-11: Var set to "YES" (uppercase) → return 1
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is 'YES' (uppercase)" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=YES
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-NOOP-12: Var set to "TRUE" (uppercase) → return 1
# ---------------------------------------------------------------------------
@test "returns 1 when the named env var is 'TRUE' (uppercase)" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=TRUE
    check_bypass_gate MY_GATE_VAR
    echo \$?
  ")
  [[ "$result" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-VARNAME: The function reads the NAMED variable, not a positional arg
# Two different variable names with different values — only the "1" one bypasses
# ---------------------------------------------------------------------------
@test "reads the named variable, not a positional: correct var bypasses, other does not" {
  result_bypass=$(bash -c "
    source '$HELPER'
    export GATE_A=1
    export GATE_B=0
    check_bypass_gate GATE_A
    echo \$?
  ")
  result_nobypass=$(bash -c "
    source '$HELPER'
    export GATE_A=1
    export GATE_B=0
    check_bypass_gate GATE_B
    echo \$?
  ")
  [[ "$result_bypass" -eq 0 ]]
  [[ "$result_nobypass" -eq 1 ]]
}

# ---------------------------------------------------------------------------
# AC-IDEMPOTENT: Calling the function multiple times on the same var is stable
# ---------------------------------------------------------------------------
@test "calling the function twice on the same var gives consistent results" {
  result=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=1
    check_bypass_gate MY_GATE_VAR
    r1=\$?
    check_bypass_gate MY_GATE_VAR
    r2=\$?
    echo \"\$r1 \$r2\"
  ")
  [[ "$result" == "0 0" ]]
}

# ---------------------------------------------------------------------------
# AC-NOOUTPUT: The function itself produces no stdout when returning 0
# ---------------------------------------------------------------------------
@test "the function produces no stdout when returning 0 (bypass)" {
  stdout=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=1
    check_bypass_gate MY_GATE_VAR
  ")
  [[ -z "$stdout" ]]
}

# ---------------------------------------------------------------------------
# AC-NOOUTPUT2: The function itself produces no stdout when returning 1
# ---------------------------------------------------------------------------
@test "the function produces no stdout when returning 1 (no bypass)" {
  # Use || true to prevent bats set-e from failing on the non-zero exit of
  # check_bypass_gate (which returns 1 for non-bypass — this is expected).
  stdout=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=false
    check_bypass_gate MY_GATE_VAR
  " || true)
  [[ -z "$stdout" ]]
}

# ---------------------------------------------------------------------------
# AC-NOOUTPUT3: The function produces no stderr on any call
# ---------------------------------------------------------------------------
@test "the function produces no stderr regardless of env var value" {
  # Capture stderr only; suppress stdout; || true absorbs the expected rc=1.
  stderr_bypass=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=1
    check_bypass_gate MY_GATE_VAR
  " 2>&1 1>/dev/null || true)
  stderr_noop=$(bash -c "
    source '$HELPER'
    export MY_GATE_VAR=false
    check_bypass_gate MY_GATE_VAR
  " 2>&1 1>/dev/null || true)
  [[ -z "$stderr_bypass" ]]
  [[ -z "$stderr_noop" ]]
}
