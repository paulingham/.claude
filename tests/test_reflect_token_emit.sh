#!/usr/bin/env bash
# Tests for hooks/reflect-token-emit.sh.
#
# Contract:
#   * Sanitizes $DEVIATION_ID against [^A-Za-z0-9_-] to prevent path traversal.
#   * Emits a JSON token at $DIR/<sanitized>.json with acknowledged=false.

set -u

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/hooks/reflect-token-emit.sh"
FAIL=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; FAIL=1; }

# Path-traversal input must NOT escape reflect-tokens/ — sanitized to "___foo".
TMP="$(mktemp -d)"
export HOME="$TMP"
export CLAUDE_SESSION_ID="test-session"
DIR="$HOME/.claude/metrics/test-session/reflect-tokens"

"$SCRIPT" "../foo" >/dev/null 2>&1
rc=$?

if [[ $rc -ne 0 ]]; then
  fail "deviation_id sanitization: script exit nonzero rc=$rc"
elif [[ -f "$DIR/___foo.json" ]]; then
  pass "deviation_id sanitization: ../foo -> ___foo.json"
else
  fail "deviation_id sanitization: expected $DIR/___foo.json; tree=$(find "$TMP" -type f 2>&1)"
fi

# Confirm no file escaped to parent dir.
if [[ -e "$HOME/.claude/metrics/test-session/foo.json" ]] || [[ -e "$HOME/.claude/metrics/foo.json" ]]; then
  fail "deviation_id sanitization: file escaped reflect-tokens/"
else
  pass "deviation_id sanitization: no file escaped reflect-tokens/"
fi

# Normal id still works.
"$SCRIPT" "normal-id" >/dev/null 2>&1
if [[ -f "$DIR/normal-id.json" ]]; then
  pass "deviation_id sanitization: normal-id passes through"
else
  fail "deviation_id sanitization: normal-id missing"
fi

rm -rf "$TMP"
exit $FAIL
