#!/usr/bin/env bash
# Test harness for skills/eval-model-effectiveness/analyze.py
# Hermetic: all obs/costs/out paths are in a mktemp tmpdir. Never touches
# real ~/.claude/learning or ~/.claude/metrics data.

set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../skills/eval-model-effectiveness" && pwd)"
ANALYZE="$SKILL_DIR/analyze.py"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

echo "=== eval-model-effectiveness Test Harness ==="
echo ""

TMP=$(mktemp -d -t eval-model-XXXXXX)
OBS="$TMP/obs.jsonl"
COSTS="$TMP/costs.jsonl"
OUT="$TMP/report.md"
: > "$OBS"
: > "$COSTS"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# Seed helper: seed_cell <role> <model> <classification> <n_obs> <cost_per_pipeline> <review_rounds> <rework:true|false>
seed_cell() {
  local role="$1" model="$2" cls="$3" n="$4" cost="$5" rounds="$6" rework="$7"
  local i pid
  for (( i=1; i<=n; i++ )); do
    pid="pid-${role}-${model}-${cls}-${i}"
    printf '{"record_type":"pipeline","pipeline_id":"%s","classification":"%s","phases":{"review":{"rounds":%d}},"rework":%s}\n' \
      "$pid" "$cls" "$rounds" "$rework" >> "$OBS"
    printf '{"pipeline_id":"%s","agent_role":"%s","model":"%s","total_cost_usd":%s}\n' \
      "$pid" "$role" "$model" "$cost" >> "$COSTS"
  done
}

# Seed a mixed cell where most obs match the (rounds, rework) pair and some override.
# Args: role model cls n_total cost rounds_main rework_main n_override rounds_ov rework_ov
seed_cell_mixed() {
  local role="$1" model="$2" cls="$3" n="$4" cost="$5" rmain="$6" wmain="$7" nov="$8" rov="$9" wov="${10}"
  local i pid rounds rework
  for (( i=1; i<=n; i++ )); do
    pid="pid-${role}-${model}-${cls}-${i}"
    if (( i <= nov )); then
      rounds="$rov"; rework="$wov"
    else
      rounds="$rmain"; rework="$wmain"
    fi
    printf '{"record_type":"pipeline","pipeline_id":"%s","classification":"%s","phases":{"review":{"rounds":%d}},"rework":%s}\n' \
      "$pid" "$cls" "$rounds" "$rework" >> "$OBS"
    printf '{"pipeline_id":"%s","agent_role":"%s","model":"%s","total_cost_usd":%s}\n' \
      "$pid" "$role" "$model" "$cost" >> "$COSTS"
  done
}

# ---- Seed all test cells ---------------------------------------------------
# 1) qa-engineer / feature: downgrade opus → sonnet
#    opus: 12 obs, 10 clean + 2 rounds=2 rework=false, cost $0.60 each
#    sonnet: 12 obs, all clean rework=false, cost $0.15 each
seed_cell_mixed "qa-engineer" "claude-opus-4-7" "feature" 12 "0.60" 1 "false" 2 2 "false"
seed_cell        "qa-engineer" "claude-sonnet-4-6" "feature" 12 "0.15" 1 "false"

# 2) architect / feature: would otherwise be downgrade — must be LOCKED
seed_cell "architect" "claude-opus-4-7"     "feature" 12 "0.80" 1 "false"
seed_cell "architect" "claude-sonnet-4-6"   "feature" 12 "0.10" 1 "false"

# 3) security-engineer / feature: would otherwise be downgrade — must be LOCKED
seed_cell "security-engineer" "claude-opus-4-7"   "feature" 12 "0.80" 1 "false"
seed_cell "security-engineer" "claude-sonnet-4-6" "feature" 12 "0.10" 1 "false"

# 4) code-reviewer / bug: insufficient data (5 + 5)
seed_cell "code-reviewer" "claude-opus-4-7"   "bug" 5 "0.50" 1 "false"
seed_cell "code-reviewer" "claude-sonnet-4-6" "bug" 5 "0.20" 1 "false"

# 5) software-engineer / refactor: no-change (sonnet not cheap enough)
#    opus: 12 obs cost $0.60/pipeline, sonnet: 12 obs cost $0.45/pipeline
#    both success ~0.90, but 0.45 is not < 0.6 * 0.60 = 0.36 → NO CHANGE
seed_cell "software-engineer" "claude-opus-4-7"   "refactor" 12 "0.60" 1 "false"
seed_cell "software-engineer" "claude-sonnet-4-6" "refactor" 12 "0.45" 1 "false"

# ---- Run analyser ----------------------------------------------------------
echo "-- analyser run --"
OUT_STDOUT=$(python3 "$ANALYZE" --obs-path "$OBS" --costs-path "$COSTS" --out "$OUT" 2>"$TMP/stderr"); RC=$?
if [[ $RC -eq 0 ]]; then
  pass "analyzer: exits 0 on valid input"
else
  fail "analyzer: exits 0 on valid input" "0" "$RC"
  cat "$TMP/stderr" >&2
fi

REPORT="$(cat "$OUT")"

# ---- Assert 1: downgrade signal --------------------------------------------
echo ""
echo "-- downgrade signal --"
if grep -q "qa-engineer / feature: DOWNGRADE opus → sonnet" "$OUT"; then
  pass "downgrade: qa-engineer / feature flagged opus → sonnet"
else
  fail "downgrade: qa-engineer / feature flagged opus → sonnet" "match" "no match"
  grep -n "qa-engineer" "$OUT" || true
fi
if grep -qE "^### qa-engineer / feature" "$OUT" && \
   grep -qE "^- opus: 12 obs" "$OUT" && \
   grep -qE "^- sonnet: 12 obs" "$OUT" && \
   grep -q "cost delta (cheaper vs current):" "$OUT"; then
  pass "downgrade: evidence block contains opus+sonnet rows and cost delta"
else
  fail "downgrade: evidence block contains opus+sonnet rows and cost delta" "all 4 markers" "missing"
fi

# ---- Assert 2: architect lockout -------------------------------------------
echo ""
echo "-- architect lockout --"
if grep -q "architect / feature: LOCKED" "$OUT"; then
  pass "lockout: architect / feature marked LOCKED"
else
  fail "lockout: architect / feature marked LOCKED" "LOCKED line" "missing"
fi
if grep -qE "^### architect" "$OUT"; then
  fail "lockout: architect has NO evidence block" "no block" "block present"
else
  pass "lockout: architect has no evidence block"
fi

# ---- Assert 3: security-engineer lockout -----------------------------------
echo ""
echo "-- security-engineer lockout --"
if grep -q "security-engineer / feature: LOCKED" "$OUT"; then
  pass "lockout: security-engineer / feature marked LOCKED"
else
  fail "lockout: security-engineer / feature marked LOCKED" "LOCKED line" "missing"
fi
if grep -qE "^### security-engineer" "$OUT"; then
  fail "lockout: security-engineer has NO evidence block" "no block" "block present"
else
  pass "lockout: security-engineer has no evidence block"
fi

# ---- Assert 4: insufficient data -------------------------------------------
echo ""
echo "-- insufficient data --"
if grep -q "code-reviewer / bug: INSUFFICIENT_DATA" "$OUT"; then
  pass "insufficient: code-reviewer / bug flagged INSUFFICIENT_DATA"
else
  fail "insufficient: code-reviewer / bug flagged INSUFFICIENT_DATA" "line" "missing"
fi
if grep -q "code-reviewer / bug: DOWNGRADE" "$OUT"; then
  fail "insufficient: code-reviewer / bug NOT downgraded" "no downgrade" "downgrade present"
else
  pass "insufficient: code-reviewer / bug NOT downgraded"
fi

# ---- Assert 5: no-change signal --------------------------------------------
echo ""
echo "-- no-change signal --"
if grep -q "software-engineer / refactor: NO CHANGE" "$OUT"; then
  pass "no-change: software-engineer / refactor flagged NO CHANGE"
else
  fail "no-change: software-engineer / refactor flagged NO CHANGE" "line" "missing"
  grep -n "software-engineer" "$OUT" || true
fi

# ---- Assert 6: verdict line ------------------------------------------------
echo ""
echo "-- verdict --"
if [[ "$OUT_STDOUT" == "VERDICT: RECOMMENDATIONS_READY" ]]; then
  pass "verdict: RECOMMENDATIONS_READY"
else
  fail "verdict: RECOMMENDATIONS_READY" "VERDICT: RECOMMENDATIONS_READY" "$OUT_STDOUT"
fi

# ---- Assert 7: file produced with all three sections -----------------------
echo ""
echo "-- report structure --"
if [[ -f "$OUT" ]]; then
  pass "report: file produced"
else
  fail "report: file produced" "file exists" "missing"
fi
for header in "== Summary ==" "== Evidence ==" "== How to apply =="; do
  if grep -qF "$header" "$OUT"; then
    pass "report: contains '$header'"
  else
    fail "report: contains '$header'" "header" "missing"
  fi
done

# ---- Assert 8: schema error ------------------------------------------------
echo ""
echo "-- schema error --"
BAD_OBS="$TMP/bad-obs.jsonl"
printf '{"record_type":"pipeline","pipeline_id":"bad-1","classification":"feature"}\n' > "$BAD_OBS"
BAD_COSTS="$TMP/bad-costs.jsonl"
printf '{"pipeline_id":"bad-1","agent_role":"qa-engineer","model":"sonnet","total_cost_usd":0.1}\n' > "$BAD_COSTS"
BAD_OUT="$TMP/bad-report.md"
set +e
BAD_STDERR=$(python3 "$ANALYZE" --obs-path "$BAD_OBS" --costs-path "$BAD_COSTS" --out "$BAD_OUT" 2>&1 >/dev/null)
BAD_RC=$?
set -e
if [[ $BAD_RC -eq 2 ]]; then
  pass "schema: exits 2 on malformed pipeline record"
else
  fail "schema: exits 2 on malformed pipeline record" "2" "$BAD_RC"
fi
if echo "$BAD_STDERR" | grep -q "SCHEMA_ERROR"; then
  pass "schema: stderr contains SCHEMA_ERROR"
else
  fail "schema: stderr contains SCHEMA_ERROR" "SCHEMA_ERROR" "$BAD_STDERR"
fi

# ---- Summary ---------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
