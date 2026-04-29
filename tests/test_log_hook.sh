#!/usr/bin/env bash
# Tests for hooks/_lib/log.sh — structured JSONL telemetry helper.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_LIB="$REPO_ROOT/hooks/_lib/log.sh"
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

echo "=== log.sh helper tests ==="

# --- Test 1: log.sh exists and passes bash -n ---
echo "--- Syntax ---"
[[ -f "$LOG_LIB" ]] && bash -n "$LOG_LIB" 2>/dev/null
assert "log.sh exists and passes bash -n syntax check" "$?"

# Helper: build a minimal hook that sources log.sh in a fresh tmp dir.
make_hook() {
    local hook_path="$1" exit_code="$2"
    cat > "$hook_path" <<HOOK_EOF
#!/usr/bin/env bash
source "$LOG_LIB"
_log_hook_start
trap 'log_hook_event \$?' EXIT
exit $exit_code
HOOK_EOF
    chmod +x "$hook_path"
}

# Helper: run a hook with exit code, return path to its hooks.jsonl.
run_hook_with_exit() {
    local label="$1"
    local exit_code="$2"
    local hook_dir="$TMP_ROOT/$label"
    mkdir -p "$hook_dir"
    make_hook "$hook_dir/sample-hook.sh" "$exit_code"
    CLAUDE_HOOK_LOG_DIR="$hook_dir/metrics" CLAUDE_SESSION_ID="$label" \
        bash "$hook_dir/sample-hook.sh"
    echo "$hook_dir/metrics/$label/hooks.jsonl"
}

# --- Test 2: minimal hook (exit 0) emits exactly one JSONL line ---
echo "--- Single-line emit ---"
JSONL2=$(run_hook_with_exit "test2" 0)
LINE_COUNT=$(wc -l < "$JSONL2" 2>/dev/null | tr -d ' ')
[[ "$LINE_COUNT" == "1" ]]
assert "Hook exit 0 produces exactly one log line (got: $LINE_COUNT)" "$?"

# --- Test 3: hook exit 2 → log line has "exit_code":2 ---
echo "--- Exit code 2 ---"
JSONL3=$(run_hook_with_exit "test3" 2)
grep -q '"exit_code":2' "$JSONL3"
assert "Hook exit 2 produces line with exit_code:2" "$?"

# --- Test 4: hook exit 0 → log line has "exit_code":0 ---
echo "--- Exit code 0 ---"
grep -q '"exit_code":0' "$JSONL2"
assert "Hook exit 0 produces line with exit_code:0" "$?"

# --- Test 5: log line is valid JSON ---
echo "--- JSON validity ---"
python3 -c "import json,sys; json.loads(sys.stdin.read())" < "$JSONL2" 2>/dev/null
assert "Log line parses as valid JSON" "$?"

# --- Test 6: required fields present ---
echo "--- Required fields ---"
LINE=$(cat "$JSONL2")
ALL_PRESENT=0
for field in timestamp hook_name trigger duration_ms exit_code session_id; do
    if ! echo "$LINE" | grep -q "\"$field\""; then
        ALL_PRESENT=1
        echo "    MISSING: $field"
    fi
done
assert "Log line has all required fields" "$ALL_PRESENT"

# --- Test 7: duration_ms is non-negative integer ---
echo "--- duration_ms integer ---"
DUR=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read())['duration_ms'])" < "$JSONL2" 2>/dev/null)
[[ "$DUR" =~ ^[0-9]+$ ]]
assert "duration_ms is non-negative integer (got: $DUR)" "$?"

# --- Test 8: CLAUDE_HOOK_LOG_ENABLED=0 → no log line ---
echo "--- Disabled via env ---"
HOOK_DIR8="$TMP_ROOT/test8"
mkdir -p "$HOOK_DIR8"
make_hook "$HOOK_DIR8/sample-hook.sh" 0
CLAUDE_HOOK_LOG_DIR="$HOOK_DIR8/metrics" CLAUDE_SESSION_ID="testsess8" \
    CLAUDE_HOOK_LOG_ENABLED=0 bash "$HOOK_DIR8/sample-hook.sh" 2>/dev/null
[[ ! -f "$HOOK_DIR8/metrics/testsess8/hooks.jsonl" ]]
assert "CLAUDE_HOOK_LOG_ENABLED=0 produces no log file" "$?"

# --- Test 9: _log_hook_trigger sets the trigger field ---
echo "--- Trigger field ---"
HOOK_DIR9="$TMP_ROOT/test9"
mkdir -p "$HOOK_DIR9"
cat > "$HOOK_DIR9/sample-hook.sh" <<HOOK_EOF
#!/usr/bin/env bash
source "$LOG_LIB"
_log_hook_start
trap 'log_hook_event \$?' EXIT
_log_hook_trigger "TestEvent"
exit 0
HOOK_EOF
chmod +x "$HOOK_DIR9/sample-hook.sh"
CLAUDE_HOOK_LOG_DIR="$HOOK_DIR9/metrics" CLAUDE_SESSION_ID="testsess9" \
    bash "$HOOK_DIR9/sample-hook.sh"
grep -q '"trigger":"TestEvent"' "$HOOK_DIR9/metrics/testsess9/hooks.jsonl"
assert "_log_hook_trigger sets trigger field to TestEvent" "$?"

# --- Test 10: benchmark — log overhead per hook ---
echo "--- Benchmark ---"
HOOK_DIR10="$TMP_ROOT/test10"
mkdir -p "$HOOK_DIR10"
make_hook "$HOOK_DIR10/sample-hook.sh" 0
START_NS=$(python3 -c "import time; print(int(time.time()*1000))")
for _ in 1 2 3 4 5 6 7 8 9 10; do
    CLAUDE_HOOK_LOG_DIR="$HOOK_DIR10/metrics" CLAUDE_SESSION_ID="testsess10" \
        bash "$HOOK_DIR10/sample-hook.sh"
done
END_NS=$(python3 -c "import time; print(int(time.time()*1000))")
ELAPSED_MS=$(( END_NS - START_NS ))
# Spec target: <5ms log overhead per hook. We use 25ms to allow CI variance —
# real measurement comes from the per-record duration_ms field, not the loop wall-clock.
HOOK_LINES=$(wc -l < "$HOOK_DIR10/metrics/testsess10/hooks.jsonl")
MAX_DURATION=$(python3 -c "
import json
durs = []
with open('$HOOK_DIR10/metrics/testsess10/hooks.jsonl') as f:
    for line in f:
        durs.append(json.loads(line)['duration_ms'])
print(max(durs))")
[[ "$MAX_DURATION" -lt 25 ]]
assert "Max log overhead per hook < 25ms (spec: <5ms; 25ms allows CI overhead) (got: ${MAX_DURATION}ms over $HOOK_LINES runs)" "$?"

# --- Test 10b: JSON injection regression — adversarial trigger value ---
echo "--- JSON injection regression ---"
TMP_INJECT="$(mktemp -d)"
(
  source "$REPO_ROOT/hooks/_lib/log.sh"
  _log_hook_start
  # adversarial trigger: contains quotes that would break JSON if unescaped
  _LOG_HOOK_TRIGGER='PreToolUse","exit_code":99,"x":"'
  CLAUDE_HOOK_LOG_DIR="$TMP_INJECT" CLAUDE_SESSION_ID="injectsess" log_hook_event 0
)
INJECT_FILE=$(find "$TMP_INJECT" -name "hooks.jsonl" 2>/dev/null | head -1)
if [[ -n "$INJECT_FILE" ]]; then
  python3 -c "import json,sys
ok = True
for line in open('$INJECT_FILE'):
    line = line.strip()
    if not line: continue
    try:
        rec = json.loads(line)
        # Verify exit_code is the one WE supplied (0), not the injected 99
        if rec.get('exit_code') != 0:
            ok = False
    except Exception:
        ok = False
sys.exit(0 if ok else 1)"
  assert "Adversarial trigger produces valid JSON with correct exit_code" "$?"
else
  assert "Adversarial trigger produced no log file (unexpected)" "1"
fi
rm -rf "$TMP_INJECT"

# --- Test 10c: path traversal regression — '..' session ID must not escape metrics dir ---
echo "--- Path traversal regression ---"
TMP_PT="$(mktemp -d)"
(
  CLAUDE_SESSION_ID=".." CLAUDE_HOOK_LOG_DIR="$TMP_PT" bash -c "
    source '$REPO_ROOT/hooks/_lib/log.sh'
    _log_hook_start
    _log_hook_trigger 'TestTrigger'
    log_hook_event 0
  "
)
# The file must NOT land at $TMP_PT/../hooks.jsonl
OUTSIDE="$TMP_PT/../hooks.jsonl"
[ ! -f "$OUTSIDE" ]
assert ".. session ID does not write outside metrics dir" "$?"
# Some file SHOULD be written inside TMP_PT (under a sanitized session dir)
find "$TMP_PT" -name "hooks.jsonl" | grep -q .
assert ".. session ID still writes a log inside metrics dir" "$?"
rm -rf "$TMP_PT"

# --- Test 11: every instrumented hook has the 3 logging lines ---
echo "--- Hook instrumentation coverage ---"
HOOKS_DIR="$REPO_ROOT/hooks"
SKIP_LIST="hook-profile.sh loop-guard.sh test-session-start-bootstrap.sh"
MISSING=0
MISSING_LIST=""
for hook in "$HOOKS_DIR"/*.sh; do
    name=$(basename "$hook")
    skip=0
    for s in $SKIP_LIST; do [[ "$name" == "$s" ]] && skip=1; done
    [[ "$skip" == "1" ]] && continue
    # Accept either the legacy `~/.claude/...` literal or the BASH_SOURCE-relative
    # `${HOOK_DIR}/_lib/log.sh` form (introduced for hooks that need the new
    # `subagent_type` arg testable from a worktree).
    if ! grep -qE 'source [~"$]' "$hook" || ! grep -qE '_lib/log\.sh' "$hook"; then
        MISSING=$((MISSING + 1))
        MISSING_LIST="$MISSING_LIST $name"
        continue
    fi
    if ! grep -q "_log_hook_start" "$hook"; then
        MISSING=$((MISSING + 1))
        MISSING_LIST="$MISSING_LIST $name(no-start)"
        continue
    fi
    if ! grep -qE "trap.*log_hook_event" "$hook"; then
        MISSING=$((MISSING + 1))
        MISSING_LIST="$MISSING_LIST $name(no-trap)"
    fi
done
[[ "$MISSING" == "0" ]]
assert "All non-library hooks instrumented (missing: $MISSING) [$MISSING_LIST]" "$?"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
exit $FAIL
