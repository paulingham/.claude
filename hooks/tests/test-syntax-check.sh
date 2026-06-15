#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_syntax_check.bats
# Tests for syntax-check.sh (PostToolUse BLOCKING syntax gate)
# Verifies the hook rejects (exit 2) un-parseable code before it lands and
# stays out of the way (exit 0) for valid code, unsupported files, missing
# toolchains, and the two env hatches.
#
# Run from repo root: bash hooks/tests/test-syntax-check.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$HOOKS_DIR/syntax-check.sh"
# The hook sources _lib/log.sh, hook-profile.sh, loop-guard.sh relative to
# CLAUDE_PLUGIN_ROOT/hooks. Point it at the repo this test lives in so those
# libs resolve (mirrors the plugin-install layout at runtime).
export CLAUDE_PLUGIN_ROOT="$(cd "$HOOKS_DIR/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$((FAIL + 1)); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" -eq "$expected" ]]; then
    pass "$name"
  else
    fail "$name" "$expected" "$actual"
  fi
}

# Pipe a synthesized PostToolUse payload to the hook and echo its exit code.
# Reads optional pre-set env (CLAUDE_SYNTAX_CHECK / CLAUDE_SYNTAX_CHECK_SKIP_LANGS)
# from the caller's environment.
run_syntax() {
  local path="$1"
  jq -nc --arg fp "$path" \
    '{tool_name:"Write",tool_input:{file_path:$fp},hook_event_name:"PostToolUse"}' \
    | bash "$HOOK" > /dev/null 2>&1
  echo $?
}

echo "=== syntax-check Test Harness ==="
echo ""

SC_TMP=$(mktemp -d)
trap 'rm -rf "$SC_TMP"' EXIT

# Hermetic loop-guard state — without this the shared per-install guard file
# accumulates across the many invocations below and trips the re-entrancy
# limit, silently turning blocking cases into exit 0. (See hooks/loop-guard.sh.)
export CLAUDE_STATE_DIR="$SC_TMP/state"

# -- Syntax check (the hook itself must parse) --------------------------------
echo "-- syntax --"
bash -n "$HOOK" > /dev/null 2>&1
run_test "syntax-check.sh parses" 0 $?

# -- Python -------------------------------------------------------------------
echo "-- python --"
if command -v python3 &> /dev/null; then
  VALID_PY="$SC_TMP/valid.py"
  printf 'def f(x):\n    return x + 1\n' > "$VALID_PY"
  run_test "valid python -> allow (exit 0)" 0 "$(run_syntax "$VALID_PY")"

  BAD_PY="$SC_TMP/bad.py"
  printf 'def f(:\n    return 1\n' > "$BAD_PY"
  run_test "invalid python -> block (exit 2)" 2 "$(run_syntax "$BAD_PY")"
else
  pass "python tests skipped (python3 absent)"
  pass "python tests skipped (python3 absent)"
fi

# -- JSON ---------------------------------------------------------------------
echo "-- json --"
if command -v jq &> /dev/null; then
  VALID_JSON="$SC_TMP/valid.json"
  printf '{"a": 1, "b": [2, 3]}\n' > "$VALID_JSON"
  run_test "valid json -> allow (exit 0)" 0 "$(run_syntax "$VALID_JSON")"

  BAD_JSON="$SC_TMP/bad.json"
  printf '{"a": 1, "b": [2, 3}\n' > "$BAD_JSON"
  run_test "invalid json -> block (exit 2)" 2 "$(run_syntax "$BAD_JSON")"
else
  pass "json tests skipped (jq absent)"
  pass "json tests skipped (jq absent)"
fi

# -- Bash ---------------------------------------------------------------------
echo "-- bash --"
BAD_SH="$SC_TMP/bad.sh"
printf '#!/usr/bin/env bash\nif then fi\n' > "$BAD_SH"
run_test "invalid bash -> block (exit 2)" 2 "$(run_syntax "$BAD_SH")"

VALID_SH="$SC_TMP/valid.sh"
printf '#!/usr/bin/env bash\nif true; then echo ok; fi\n' > "$VALID_SH"
run_test "valid bash -> allow (exit 0)" 0 "$(run_syntax "$VALID_SH")"

# -- Unsupported extension ----------------------------------------------------
echo "-- unsupported extension --"
MD_FILE="$SC_TMP/notes.md"
printf '# Heading\n\nsome text\n' > "$MD_FILE"
run_test "unsupported .md -> skip (exit 0)" 0 "$(run_syntax "$MD_FILE")"

# -- Non-existent file --------------------------------------------------------
echo "-- non-existent file --"
run_test "deleted/missing file -> skip (exit 0)" 0 "$(run_syntax "$SC_TMP/does-not-exist.py")"

# -- Global env hatch (CLAUDE_SYNTAX_CHECK=0) ---------------------------------
echo "-- global env hatch --"
if command -v python3 &> /dev/null; then
  HATCH_PY="$SC_TMP/hatch.py"
  printf 'def f(:\n    return 1\n' > "$HATCH_PY"
  GLOBAL_HATCH=$(CLAUDE_SYNTAX_CHECK=0 run_syntax "$HATCH_PY")
  run_test "CLAUDE_SYNTAX_CHECK=0 + invalid python -> allow (exit 0)" 0 "$GLOBAL_HATCH"
else
  pass "global hatch test skipped (python3 absent)"
fi

# -- Per-language opt-out (CLAUDE_SYNTAX_CHECK_SKIP_LANGS=py) ------------------
echo "-- per-language opt-out --"
if command -v python3 &> /dev/null; then
  LANG_PY="$SC_TMP/lang.py"
  printf 'def f(:\n    return 1\n' > "$LANG_PY"
  LANG_HATCH=$(CLAUDE_SYNTAX_CHECK_SKIP_LANGS=py run_syntax "$LANG_PY")
  run_test "CLAUDE_SYNTAX_CHECK_SKIP_LANGS=py + invalid python -> allow (exit 0)" 0 "$LANG_HATCH"
else
  pass "per-language opt-out test skipped (python3 absent)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
