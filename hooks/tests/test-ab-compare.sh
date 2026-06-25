#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_ab_compare.bats
# End-to-end tests for skills/internal-eval/score/ab-compare.sh.
# Covers:
#   - Path traversal rejection (Finding 1 fix)
#   - USD row rendered with real number when costs.jsonl has tagged records
#   - USD row renders disclosure string when no tagged records
#   - Tokens row present in output
#
# Hermetic: all run dirs + costs.jsonl in mktemp tmpdir; never touches real data.

set -uo pipefail

AB_COMPARE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../skills/internal-eval/score" && pwd)/ab-compare.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1"; FAIL=$(( FAIL + 1 )); }

echo "=== ab-compare.sh End-to-End Test Harness ==="
echo ""

TMP=$(mktemp -d -t ab-compare-XXXXXX)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

RUNS_DIR="$TMP/runs"
mkdir -p "$RUNS_DIR"

# ---------------------------------------------------------------------------
# Fixture: two run dirs with cases.json
# ---------------------------------------------------------------------------
mkdir -p "$RUNS_DIR/run-arm-a"
cat > "$RUNS_DIR/run-arm-a/cases.json" <<'EOF'
[
  {"pass": true, "loc_added": 10, "loc_removed": 2, "input_tokens": 1000, "output_tokens": 200},
  {"pass": true, "loc_added": 8, "loc_removed": 1, "input_tokens": 900, "output_tokens": 180}
]
EOF

mkdir -p "$RUNS_DIR/run-arm-b"
cat > "$RUNS_DIR/run-arm-b/cases.json" <<'EOF'
[
  {"pass": true, "loc_added": 3, "loc_removed": 2, "input_tokens": 500, "output_tokens": 100},
  {"pass": true, "loc_added": 2, "loc_removed": 1, "input_tokens": 450, "output_tokens": 90}
]
EOF

# ---------------------------------------------------------------------------
# Fixture: costs.jsonl WITH eval_run_id tagged records
# ---------------------------------------------------------------------------
COSTS_TAGGED="$TMP/costs-tagged.jsonl"
cat > "$COSTS_TAGGED" <<'EOF'
{"eval_run_id":"run-arm-a","task_id":"t1","usage_by_model":{"claude-sonnet-4-6":{"input_tokens":1000000,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
{"eval_run_id":"run-arm-b","task_id":"t1","usage_by_model":{"claude-sonnet-4-6":{"input_tokens":500000,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
EOF

# ---------------------------------------------------------------------------
# Fixture: costs.jsonl WITHOUT tagged records (untagged)
# ---------------------------------------------------------------------------
COSTS_UNTAGGED="$TMP/costs-untagged.jsonl"
cat > "$COSTS_UNTAGGED" <<'EOF'
{"task_id":"t2","usage_by_model":{"claude-sonnet-4-6":{"input_tokens":1000000,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
EOF

# ---------------------------------------------------------------------------
# Test 1: path traversal rejected for --arm-a
# ---------------------------------------------------------------------------
echo "--- Test: path traversal rejected for --arm-a ---"
output=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a "../../../../tmp/x" --arm-b "run-arm-b" 2>&1 || true)
exit_code=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a "../../../../tmp/x" --arm-b "run-arm-b" 2>/dev/null; echo $?)
if echo "$output" | grep -q "invalid --arm-a"; then
  pass "traversal --arm-a: stderr says invalid"
else
  fail "traversal --arm-a: expected 'invalid --arm-a' in stderr, got: $output"
fi

# ---------------------------------------------------------------------------
# Test 2: path traversal rejected for --arm-b
# ---------------------------------------------------------------------------
echo "--- Test: path traversal rejected for --arm-b ---"
output=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a "run-arm-a" --arm-b "../evil" 2>&1 || true)
if echo "$output" | grep -q "invalid --arm-b"; then
  pass "traversal --arm-b: stderr says invalid"
else
  fail "traversal --arm-b: expected 'invalid --arm-b' in stderr, got: $output"
fi

# ---------------------------------------------------------------------------
# Test 3: leading-dot run-id rejected
# ---------------------------------------------------------------------------
echo "--- Test: leading-dot run-id rejected ---"
output=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a ".hidden" --arm-b "run-arm-b" 2>&1 || true)
if echo "$output" | grep -q "invalid --arm-a"; then
  pass "leading-dot --arm-a: stderr says invalid"
else
  fail "leading-dot --arm-a: expected 'invalid --arm-a' in stderr, got: $output"
fi

# ---------------------------------------------------------------------------
# Test 4: USD row with real number when costs.jsonl has tagged records
# ---------------------------------------------------------------------------
echo "--- Test: USD row renders real number with tagged costs.jsonl ---"
OUT_DIR="$TMP/out-tagged"
output=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a "run-arm-a" --arm-b "run-arm-b" 2>&1)
report="$OUT_DIR/ab-report.md"
if [ ! -f "$report" ]; then
  # find the actual output dir
  report=$(find "$RUNS_DIR" -name "ab-report.md" 2>/dev/null | head -1)
fi
if [ -f "$report" ]; then
  if grep -q "| USD |" "$report" && ! grep -q "USD unavailable" "$report"; then
    pass "USD row: real dollar value rendered (no 'USD unavailable')"
  elif grep -q "USD unavailable" "$report"; then
    fail "USD row: got 'USD unavailable' but expected real number; report: $(cat "$report")"
  else
    fail "USD row: USD row not found in report; report: $(cat "$report")"
  fi
else
  fail "USD tagged: no ab-report.md found; output: $output"
fi

# ---------------------------------------------------------------------------
# Test 5: USD row shows disclosure when costs.jsonl has NO tagged records
# ---------------------------------------------------------------------------
echo "--- Test: USD row renders disclosure when costs.jsonl has no tagged records ---"
# Clean out any prior report
rm -rf "$RUNS_DIR/run-arm-a-vs-run-arm-b"
output=$(EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_UNTAGGED" \
  bash "$AB_COMPARE" --arm-a "run-arm-a" --arm-b "run-arm-b" 2>&1)
report=$(find "$RUNS_DIR" -name "ab-report.md" 2>/dev/null | head -1)
if [ -f "$report" ]; then
  if grep -q "USD unavailable" "$report"; then
    pass "USD unavailable: disclosure string rendered when no tagged records"
  else
    fail "USD unavailable: expected 'USD unavailable' in report; report: $(cat "$report")"
  fi
else
  fail "USD untagged: no ab-report.md found; output: $output"
fi

# ---------------------------------------------------------------------------
# Test 6: Tokens row present in output
# ---------------------------------------------------------------------------
echo "--- Test: Tokens row present in output ---"
rm -rf "$RUNS_DIR/run-arm-a-vs-run-arm-b"
EVAL_RUNS_DIR="$RUNS_DIR" EVAL_COSTS_JSONL="$COSTS_TAGGED" \
  bash "$AB_COMPARE" --arm-a "run-arm-a" --arm-b "run-arm-b" >/dev/null 2>&1 || true
report=$(find "$RUNS_DIR" -name "ab-report.md" 2>/dev/null | head -1)
if [ -f "$report" ] && grep -q "| Tokens |" "$report"; then
  pass "Tokens row: present in report"
else
  fail "Tokens row: not found in report"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
