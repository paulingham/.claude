#!/usr/bin/env bash
# Tests for scripts/hook-summary.sh — JSONL telemetry analyzer.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HS="$REPO_ROOT/scripts/hook-summary.sh"
PASS=0
FAIL=0
TOTAL=0
TMP_ROOT=""

assert() {
    local description="$1"
    local result="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$result" == "0" ]]; then
        PASS=$((PASS + 1))
        echo "  PASS: $description"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $description"
    fi
}

cleanup() {
    [[ -n "$TMP_ROOT" && -d "$TMP_ROOT" ]] && rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

TMP_ROOT="$(mktemp -d)"
SESSION_DIR="$TMP_ROOT/metrics/test-sess"
mkdir -p "$SESSION_DIR"
JSONL="$SESSION_DIR/hooks.jsonl"

# Build a fixture JSONL: 5 fast OK hooks, 1 slow hook (200ms), 2 failing hooks.
cat > "$JSONL" <<'FIXTURE'
{"timestamp":"2026-04-28T10:00:00Z","hook_name":"fast-a","trigger":"PreToolUse:Bash","duration_ms":3,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:01Z","hook_name":"fast-b","trigger":"PreToolUse:Bash","duration_ms":5,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:02Z","hook_name":"fast-c","trigger":"PostToolUse","duration_ms":7,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:03Z","hook_name":"fast-d","trigger":"Stop","duration_ms":2,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:04Z","hook_name":"fast-e","trigger":"SessionStart","duration_ms":4,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:05Z","hook_name":"slow-hook","trigger":"PreToolUse:Agent","duration_ms":200,"exit_code":0,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:06Z","hook_name":"failing-hook","trigger":"PreToolUse:Bash","duration_ms":10,"exit_code":2,"session_id":"test-sess"}
{"timestamp":"2026-04-28T10:00:07Z","hook_name":"failing-hook","trigger":"PreToolUse:Bash","duration_ms":12,"exit_code":2,"session_id":"test-sess"}
FIXTURE

EMPTY_DIR="$TMP_ROOT/empty/metrics"
mkdir -p "$EMPTY_DIR"

echo "=== hook-summary.sh tests ==="

# --- Test 1: script exists, is executable, passes bash -n ---
echo "--- Syntax & permissions ---"
[[ -f "$HS" && -x "$HS" ]] && bash -n "$HS" 2>/dev/null
assert "hook-summary.sh exists, is executable, passes bash -n" "$?"

# --- Test 2: empty input — exits 0, no errors ---
echo "--- Empty input ---"
OUT2=$(CLAUDE_HOOK_LOG_DIR="$EMPTY_DIR" bash "$HS" 2>&1)
RC2=$?
[[ "$RC2" == "0" ]]
assert "Empty input exits 0 (got: $RC2)" "$?"

# --- Test 3: default output lists slowest hooks (slow-hook should be #1) ---
echo "--- Slowest hooks ---"
OUT3=$(CLAUDE_HOOK_LOG_DIR="$TMP_ROOT/metrics" bash "$HS" 2>&1)
echo "$OUT3" | grep -q "slow-hook"
assert "Default output mentions slow-hook" "$?"

# --- Test 4: default output shows failure counts ---
echo "--- Failure counts ---"
echo "$OUT3" | grep -q "failing-hook"
assert "Default output mentions failing-hook" "$?"

# --- Test 5: --anomaly-check with default threshold (0.10) flags failing-hook ---
# failing-hook has 2/2 invocations exit_code=2 → 100% error rate, exceeds 10% default.
# slow-hook has 1/1 invocations exit_code=0 → 0% error rate, not flagged.
echo "--- Anomaly check (error-rate semantics) ---"
OUT5=$(CLAUDE_HOOK_LOG_DIR="$TMP_ROOT/metrics" bash "$HS" --anomaly-check 2>&1)
RC5=$?
# Must mention ANOMALY (case-insensitive) AND failing-hook AND exit non-zero on detection
{ [[ "$RC5" != "0" ]] && echo "$OUT5" | grep -qi "anomaly" && echo "$OUT5" | grep -q "failing-hook"; }
assert "--anomaly-check flags failing-hook at default threshold 0.10 (rc=$RC5)" "$?"

# --- Test 6: --threshold 1.1 (110% — impossible) makes nothing an anomaly ---
echo "--- Custom threshold ---"
OUT6=$(CLAUDE_HOOK_LOG_DIR="$TMP_ROOT/metrics" bash "$HS" --anomaly-check --threshold 1.1 2>&1)
RC6=$?
[[ "$RC6" == "0" ]]
assert "--threshold 1.1 produces clean run (rc=$RC6)" "$?"

# --- Test 7: --last-n 2 limits slowest table output ---
echo "--- last-n flag ---"
OUT7=$(CLAUDE_HOOK_LOG_DIR="$TMP_ROOT/metrics" bash "$HS" --last-n 2 2>&1)
RC7=$?
# Must (a) succeed, (b) mention slow-hook (still in top-N), (c) have <= 2 hook rows
SLOW_COUNT=$(echo "$OUT7" | awk '/Slowest/,/^$/' | grep -E "[a-z]+-(hook|[a-e])" | wc -l | tr -d ' ')
{ [[ "$RC7" == "0" ]] && echo "$OUT7" | grep -q "slow-hook" && [[ "$SLOW_COUNT" -ge "1" && "$SLOW_COUNT" -le "2" ]]; }
assert "--last-n 2 limits slowest output to <= 2 rows (got: $SLOW_COUNT, rc=$RC7)" "$?"

# --- Test 7b: CLAUDE_HOOK_ANOMALY_THRESHOLD env var overrides default ---
echo "--- Env threshold override ---"
OUT7b=$(CLAUDE_HOOK_LOG_DIR="$TMP_ROOT/metrics" CLAUDE_HOOK_ANOMALY_THRESHOLD=1.1 bash "$HS" --anomaly-check 2>&1)
RC7b=$?
[[ "$RC7b" == "0" ]]
assert "CLAUDE_HOOK_ANOMALY_THRESHOLD=1.1 produces clean run (rc=$RC7b)" "$?"

# --- Test 8: session-start-bootstrap.sh integrates anomaly hint section ---
echo "--- Bootstrap integration ---"
BOOTSTRAP="$REPO_ROOT/hooks/session-start-bootstrap.sh"
{ grep -q "Hook anomaly" "$BOOTSTRAP" \
    && grep -q "hook-summary.sh" "$BOOTSTRAP" \
    && BS_ANOM=$(grep -n "Hook anomaly" "$BOOTSTRAP" | head -1 | cut -d: -f1) \
    && BS_WT=$(grep -n "Stale worktree detection" "$BOOTSTRAP" | head -1 | cut -d: -f1) \
    && BS_IRON=$(grep -n "IRON LAWS:" "$BOOTSTRAP" | head -1 | cut -d: -f1) \
    && [[ "$BS_ANOM" -gt "$BS_WT" && "$BS_ANOM" -lt "$BS_IRON" ]]; }
assert "Bootstrap includes hook anomaly section between stale-worktree and IRON LAWS" "$?"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
exit $FAIL
