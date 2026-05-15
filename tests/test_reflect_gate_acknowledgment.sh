#!/usr/bin/env bash
# Tests for hooks/reflect-gate-acknowledgment.sh.
#
# Contract:
#   * Scans $1 (or $HOME/.claude/metrics/$CLAUDE_SESSION_ID/reflect-tokens) for *.json
#   * Each token with acknowledged: false -> exit 1 + stderr listing the blockers
#   * All tokens acknowledged OR no tokens -> exit 0 silent
#   * Malformed JSON -> exit 1 + error message

set -u

SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/hooks/reflect-gate-acknowledgment.sh"
FAIL=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; FAIL=1; }

setup_tmp() {
  TMPDIR_T="$(mktemp -d)"
  echo "$TMPDIR_T"
}

teardown() { rm -rf "$1"; }

# 1. No tokens -> exit 0 silent
T=$(setup_tmp)
out=$("$SCRIPT" "$T" 2>&1); rc=$?
if [[ $rc -eq 0 && -z "$out" ]]; then pass "no tokens -> exit 0 silent"
else fail "no tokens: rc=$rc out=$out"; fi
teardown "$T"

# 2. All acknowledged -> exit 0
T=$(setup_tmp)
echo '{"deviation_id":"a","acknowledged":true}' > "$T/a.json"
echo '{"deviation_id":"b","acknowledged":true}' > "$T/b.json"
out=$("$SCRIPT" "$T" 2>&1); rc=$?
if [[ $rc -eq 0 ]]; then pass "all acknowledged -> exit 0"
else fail "all acknowledged: rc=$rc out=$out"; fi
teardown "$T"

# 3. One unacknowledged -> exit 1 + names it
T=$(setup_tmp)
echo '{"deviation_id":"a","acknowledged":true}' > "$T/a.json"
echo '{"deviation_id":"b","acknowledged":false}' > "$T/b.json"
out=$("$SCRIPT" "$T" 2>&1); rc=$?
if [[ $rc -eq 1 && "$out" == *"BLOCKED"* && "$out" == *"b"* ]]; then
  pass "unacknowledged -> exit 1 + cites id"
else fail "unacknowledged: rc=$rc out=$out"; fi
teardown "$T"

# 4. Malformed JSON -> exit 1 + error
T=$(setup_tmp)
echo 'not json {{{' > "$T/bad.json"
out=$("$SCRIPT" "$T" 2>&1); rc=$?
if [[ $rc -eq 1 && "$out" == *"bad.json"* ]]; then pass "malformed -> exit 1"
else fail "malformed: rc=$rc out=$out"; fi
teardown "$T"

# 5. Rationale with ANSI escape sequences -> stripped from stderr (LOW finding).
T=$(setup_tmp)
printf '{"deviation_id":"esc","acknowledged":false,"rationale":"test\\u001b[31mred\\u001b[0m"}' > "$T/esc.json"
out=$("$SCRIPT" "$T" 2>&1); rc=$?
if [[ $rc -eq 1 && "$out" == *"testred"* && "$out" != *"[31m"* && "$out" != *"[0m"* ]] && ! printf '%s' "$out" | grep -q $'\x1b'; then
  pass "rationale escape stripping: ANSI removed from stderr"
else
  fail "rationale escape stripping: rc=$rc out=$(printf '%s' "$out" | cat -v)"
fi
teardown "$T"

# 6. Nonexistent dir -> exit 0 (treated as no tokens)
out=$("$SCRIPT" "/nonexistent/path/that/does/not/exist" 2>&1); rc=$?
if [[ $rc -eq 0 ]]; then pass "nonexistent dir -> exit 0"
else fail "nonexistent dir: rc=$rc out=$out"; fi

exit $FAIL
