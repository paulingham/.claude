#!/usr/bin/env bash
# Test harness for auto-learn-gate.sh
# Exercises: fire-on-threshold, idempotency, reset-on-learn, disable env var,
# missing-instincts-bootstrap guard, same-pipeline re-fire suppression.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_HOOK="$HOOKS_DIR/auto-learn-gate.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  [[ "$actual" -eq "$expected" ]] && pass "$name" || fail "$name" "$expected" "$actual"
}

echo "=== auto-learn-gate Test Harness ==="
echo ""

# Hermetic dir under real ~/.claude/learning — override via CLAUDE_LEARN_TEST_HASH
TEST_HASH="test-auto-learn-$$"
LEARN_DIR="$HOME/.claude/learning/$TEST_HASH"
PIPELINE_DIR="$HOME/.claude/pipeline-state"
mkdir -p "$LEARN_DIR/instincts" "$PIPELINE_DIR"

OBS_FILE="$LEARN_DIR/observations.jsonl"
STATE_FILE="$LEARN_DIR/.learn-state.json"

cleanup() {
  rm -rf "$LEARN_DIR"
  rm -f "$PIPELINE_DIR"/test-auto-learn-*-pipeline.md
}
trap cleanup EXIT

seed_observation() {
  local pid="$1"
  printf '{"record_type":"pipeline","timestamp":"2026-04-23T00:00:%02dZ","pipeline_id":"%s","classification":"feature","phases":{"build":{"verdict":"BUILD_COMPLETE"}},"rework":false}\n' \
    "$2" "$pid" >> "$OBS_FILE"
}

seed_pipeline_state() {
  local pid="$1"
  cat > "$PIPELINE_DIR/${pid}-pipeline.md" <<EOF
---
task_id: ${pid}
phase: reflect
verdict: in_progress
---
EOF
}

reset_state() {
  printf '%s' '{"last_learn_run":null,"pipelines_since_learn":0,"observations_since_learn":0,"last_fired_pipeline_id":null,"last_observation_offset":0}' > "$STATE_FILE"
}

run_hook() {
  CLAUDE_LEARN_TEST_HASH="$TEST_HASH" bash "$GATE_HOOK" <<< '{}'
}

# -- Test 1: hook exists and is executable ----------------------------------
echo "-- basic --"
if [[ -x "$GATE_HOOK" ]]; then
  pass "auto-learn-gate: hook exists and is executable"
else
  fail "auto-learn-gate: hook exists and is executable" "executable" "missing or not +x"
  echo "Results: $PASS passed, $FAIL failed"
  exit 1
fi

bash -n "$GATE_HOOK" > /dev/null 2>&1
run_test "auto-learn-gate: syntax valid" 0 $?

# -- Test 2: gate fires at threshold (3 obs, 3 pipelines) -------------------
echo ""
echo "-- gate fires --"
: > "$OBS_FILE"
reset_state
seed_observation "test-auto-learn-p1" 1
seed_pipeline_state "test-auto-learn-p1"
OUT1=$(run_hook 2>&1); RC1=$?
rm -f "$PIPELINE_DIR/test-auto-learn-p1-pipeline.md"

seed_observation "test-auto-learn-p2" 2
seed_pipeline_state "test-auto-learn-p2"
OUT2=$(run_hook 2>&1); RC2=$?
rm -f "$PIPELINE_DIR/test-auto-learn-p2-pipeline.md"

seed_observation "test-auto-learn-p3" 3
seed_pipeline_state "test-auto-learn-p3"
OUT3=$(run_hook 2>&1); RC3=$?

run_test "auto-learn-gate: 1st obs exits 0" 0 "$RC1"
run_test "auto-learn-gate: 2nd obs exits 0" 0 "$RC2"
run_test "auto-learn-gate: 3rd obs exits 0" 0 "$RC3"

if echo "$OUT1" | grep -q "Triggered"; then
  fail "auto-learn-gate: no trigger after 1st obs" "no trigger" "triggered"
else
  pass "auto-learn-gate: no trigger after 1st obs"
fi
if echo "$OUT2" | grep -q "Triggered"; then
  fail "auto-learn-gate: no trigger after 2nd obs" "no trigger" "triggered"
else
  pass "auto-learn-gate: no trigger after 2nd obs"
fi
if echo "$OUT3" | grep -q "Triggered"; then
  pass "auto-learn-gate: triggered after 3rd obs"
else
  fail "auto-learn-gate: triggered after 3rd obs" "triggered" "no trigger"
fi

OBS_COUNT=$(jq -r '.observations_since_learn' "$STATE_FILE")
PIPE_COUNT=$(jq -r '.pipelines_since_learn' "$STATE_FILE")
if [[ "$OBS_COUNT" -ge 3 && "$PIPE_COUNT" -ge 3 ]]; then
  pass "auto-learn-gate: state counters reached threshold (obs=$OBS_COUNT pipes=$PIPE_COUNT)"
else
  fail "auto-learn-gate: state counters reached threshold" "obs>=3 pipes>=3" "obs=$OBS_COUNT pipes=$PIPE_COUNT"
fi

# -- Test 3: idempotency — same pipeline does not re-fire -------------------
echo ""
echo "-- idempotency --"
OUT_REPEAT=$(run_hook 2>&1)
if echo "$OUT_REPEAT" | grep -q "Triggered"; then
  fail "auto-learn-gate: same pipeline does not re-fire" "no trigger" "re-triggered"
else
  pass "auto-learn-gate: same pipeline does not re-fire"
fi
rm -f "$PIPELINE_DIR/test-auto-learn-p3-pipeline.md"

# -- Test 4: /learn reset clears counters, no re-fire w/o new obs -----------
echo ""
echo "-- /learn reset --"
# Simulate /learn completion: reset counters but preserve offset + last_fired.
CURRENT_OFFSET=$(jq -r '.last_observation_offset' "$STATE_FILE")
CURRENT_FIRED=$(jq -r '.last_fired_pipeline_id' "$STATE_FILE")
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq -n --arg ts "$NOW" --argjson off "$CURRENT_OFFSET" --arg fp "$CURRENT_FIRED" \
  '{last_learn_run:$ts,pipelines_since_learn:0,observations_since_learn:0,last_fired_pipeline_id:$fp,last_observation_offset:$off}' \
  > "$STATE_FILE"

OUT_AFTER_LEARN=$(run_hook 2>&1)
if echo "$OUT_AFTER_LEARN" | grep -q "Triggered"; then
  fail "auto-learn-gate: no re-fire after /learn reset w/o new obs" "no trigger" "triggered"
else
  pass "auto-learn-gate: no re-fire after /learn reset w/o new obs"
fi

# -- Test 5: disable env var ------------------------------------------------
echo ""
echo "-- disable flag --"
reset_state
: > "$OBS_FILE"
seed_observation "test-auto-learn-p4" 4
seed_observation "test-auto-learn-p5" 5
seed_observation "test-auto-learn-p6" 6
OUT_DISABLED=$(CLAUDE_DISABLE_AUTO_LEARN=1 CLAUDE_LEARN_TEST_HASH="$TEST_HASH" bash "$GATE_HOOK" <<< '{}' 2>&1)
DISABLED_RC=$?
run_test "auto-learn-gate: disabled exits 0" 0 "$DISABLED_RC"
if echo "$OUT_DISABLED" | grep -q "Triggered"; then
  fail "auto-learn-gate: disabled suppresses trigger" "no trigger" "triggered"
else
  pass "auto-learn-gate: disabled suppresses trigger"
fi

# -- Test 6: missing instincts dir → WARN + no fire -------------------------
echo ""
echo "-- bootstrap check --"
reset_state
: > "$OBS_FILE"
seed_observation "test-auto-learn-p7" 7
seed_observation "test-auto-learn-p8" 8
seed_observation "test-auto-learn-p9" 9
rm -rf "$LEARN_DIR/instincts"
OUT_NO_INSTINCTS=$(run_hook 2>&1)
NI_RC=$?
run_test "auto-learn-gate: missing instincts exits 0" 0 "$NI_RC"
if echo "$OUT_NO_INSTINCTS" | grep -q "Triggered"; then
  fail "auto-learn-gate: missing instincts does not fire" "no trigger" "triggered"
else
  pass "auto-learn-gate: missing instincts does not fire"
fi
# Restore instincts dir for subsequent tests
mkdir -p "$LEARN_DIR/instincts"

# -- Test 7: tool_use records are ignored -----------------------------------
echo ""
echo "-- filter tool_use records --"
reset_state
: > "$OBS_FILE"
# Seed 5 tool_use noise records — should be ignored
for i in 1 2 3 4 5; do
  printf '{"record_type":"tool_use","tool":"Edit","timestamp":"2026-04-23T00:00:%02dZ"}\n' "$i" >> "$OBS_FILE"
done
seed_pipeline_state "test-auto-learn-noise"
OUT_NOISE=$(run_hook 2>&1)
rm -f "$PIPELINE_DIR/test-auto-learn-noise-pipeline.md"
if echo "$OUT_NOISE" | grep -q "Triggered"; then
  fail "auto-learn-gate: tool_use records ignored" "no trigger" "triggered"
else
  pass "auto-learn-gate: tool_use records ignored"
fi
OBS_COUNT=$(jq -r '.observations_since_learn' "$STATE_FILE")
if [[ "$OBS_COUNT" -eq 0 ]]; then
  pass "auto-learn-gate: tool_use records not counted (obs=0)"
else
  fail "auto-learn-gate: tool_use records not counted" "0" "$OBS_COUNT"
fi

# -- Test 8: fallback filter (no record_type but has pipeline_id+phases) ----
echo ""
echo "-- fallback filter --"
reset_state
: > "$OBS_FILE"
# Legacy observation: no record_type, but has pipeline_id+phases
printf '{"timestamp":"2026-04-23T00:00:01Z","pipeline_id":"legacy-p1","phases":{"build":{"verdict":"OK"}}}\n' >> "$OBS_FILE"
printf '{"timestamp":"2026-04-23T00:00:02Z","pipeline_id":"legacy-p2","phases":{"build":{"verdict":"OK"}}}\n' >> "$OBS_FILE"
printf '{"timestamp":"2026-04-23T00:00:03Z","pipeline_id":"legacy-p3","phases":{"build":{"verdict":"OK"}}}\n' >> "$OBS_FILE"
seed_pipeline_state "legacy-p3"
OUT_LEGACY=$(run_hook 2>&1)
rm -f "$PIPELINE_DIR/legacy-p3-pipeline.md"
if echo "$OUT_LEGACY" | grep -q "Triggered"; then
  pass "auto-learn-gate: fallback filter (no record_type) counts pipeline-shaped records"
else
  fail "auto-learn-gate: fallback filter (no record_type) counts pipeline-shaped records" "triggered" "no trigger"
fi

# -- Summary -----------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
