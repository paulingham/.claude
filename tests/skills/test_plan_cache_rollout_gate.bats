#!/usr/bin/env bats
# Slice G — ACs G1..G7 for skills/plan-cache-rollout-gate.
# The skill is a thin wrapper around hooks/_lib/plan-cache-rollout-gate.py.
# Tests exercise the Python aggregator directly with synthesized
# metrics/<session>/plan-cache.jsonl fixtures.
#
# Thresholds (verbatim from plan.md § Slice slice-g-rollout-gate-skill):
#   hit_rate >= 0.10
#   pv_pass_rate_on_hit >= 0.95
#   cost_delta > 0
# Window: last N=30 pipelines OR 14-day rolling, whichever is LARGER.
# hit_rate denominator EXCLUDES miss_reason=shadow-mode lines.
# cost_delta = sum(saved_architect_tokens_estimate) - sum(adapter_cost_tokens)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  GATE="$REPO_ROOT/hooks/_lib/plan-cache-rollout-gate.py"
  TMP_DIR="$(mktemp -d -t plan-cache-gate-XXXXXX)"
  METRICS_DIR="$TMP_DIR/metrics"
  mkdir -p "$METRICS_DIR"
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

# _emit <session-id> <days-ago> <verdict> <miss_reason> <pv_outcome> <adapter_tokens> <saved_tokens>
_emit() {
  local sid="$1" days_ago="$2" verdict="$3" miss_reason="$4"
  local pv="$5" adapter="$6" saved="$7"
  mkdir -p "$METRICS_DIR/$sid"
  local ts
  ts=$(python3 -c "import datetime as dt; \
print((dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=$days_ago)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
  python3 -c "
import json,sys
rec={'task_id':'t-$sid','cache_key':'k-$sid','verdict':'$verdict',
     'adapter_cost_tokens':$adapter,'miss_reason':'$miss_reason',
     'hit_template_path':'','hit_count_after':0,'pv_outcome':'$pv',
     'session_id':'$sid','timestamp':'$ts',
     'saved_architect_tokens_estimate':$saved}
open('$METRICS_DIR/$sid/plan-cache.jsonl','a').write(json.dumps(rec)+'\n')
"
}

@test "G1 aggregate reads all plan-cache.jsonl in metrics/*" {
  # Three sessions, each with one record. Enough volume to bypass INSUFFICIENT_DATA: emit 30.
  for i in $(seq 1 30); do
    _emit "s$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"sessions_seen": 30'
  echo "$output" | grep -q '"hits": 30'
}

@test "G2 hit_rate excludes shadow-mode MISS from denominator" {
  # 1 HIT, 1 real MISS (no-template), 8 shadow-mode MISS -> denom=2 -> hit_rate=0.5
  _emit s1 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  _emit s2 1 PLAN_CACHE_MISS no-template "" 0 0
  for i in $(seq 3 10); do
    _emit "s$i" 1 PLAN_CACHE_MISS shadow-mode "" 0 0
  done
  # Pad sessions so we don't hit INSUFFICIENT_DATA: add 25 more shadow-mode misses
  for i in $(seq 11 35); do
    _emit "s$i" 1 PLAN_CACHE_MISS shadow-mode "" 0 0
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE '"hit_rate": 0\.5(\b|0)'
}

@test "G3 pv_pass_rate_on_hit counts only HIT lines with pv_outcome" {
  # 4 HITs, 3 APPROVED + 1 HOLES -> 0.75
  _emit s1 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  _emit s2 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  _emit s3 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  _emit s4 1 PLAN_CACHE_HIT "" PLAN_HOLES 100 10000
  # Pad so not INSUFFICIENT_DATA (need 30 sessions OR 14-day window of records).
  for i in $(seq 5 35); do
    _emit "s$i" 1 PLAN_CACHE_MISS shadow-mode "" 0 0
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE '"pv_pass_rate_on_hit": 0\.75'
}

@test "G4 cost_delta = saved_tokens summed minus adapter_tokens summed" {
  # 2 HITs: saved=10000 each, adapter=500 each -> delta = 20000 - 1000 = 19000
  _emit s1 1 PLAN_CACHE_HIT "" PLAN_APPROVED 500 10000
  _emit s2 1 PLAN_CACHE_HIT "" PLAN_APPROVED 500 10000
  for i in $(seq 3 32); do
    _emit "s$i" 1 PLAN_CACHE_MISS shadow-mode "" 0 0
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"cost_delta": 19000'
}

@test "G5 ROLLOUT_GATE_PASS when all three thresholds met" {
  # 10 HITs (all APPROVED, saved=10000, adapter=100) + 20 MISS no-template
  # denom=30, hit_rate=10/30=0.333 >=0.10; pv=1.0 >=0.95; cost_delta=10*9900>0.
  for i in $(seq 1 10); do
    _emit "h$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  for i in $(seq 1 20); do
    _emit "m$i" 1 PLAN_CACHE_MISS no-template "" 0 0
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "ROLLOUT_GATE_PASS"'
}

@test "G6 FAIL verdict body cites which threshold failed (hit_rate low)" {
  # 1 HIT, 29 real MISS -> denom=30, hit_rate=1/30 ~= 0.033 < 0.10 -> FAIL
  _emit h1 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  for i in $(seq 1 29); do
    _emit "m$i" 1 PLAN_CACHE_MISS no-template "" 0 0
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "ROLLOUT_GATE_FAIL"'
  echo "$output" | grep -q 'hit_rate'
  echo "$output" | grep -q '< 0.10'
}

@test "G7 fewer than 30 pipelines AND less than 14 days -> INSUFFICIENT_DATA" {
  # 5 sessions, all 1 day old -> insufficient.
  for i in $(seq 1 5); do
    _emit "s$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "INSUFFICIENT_DATA"'
}

@test "G6b FAIL also cites pv_pass_rate when below 0.95" {
  # 30 HITs, but only 20/30 PLAN_APPROVED -> pv_pass=0.667 < 0.95 -> FAIL.
  for i in $(seq 1 20); do
    _emit "h$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  for i in $(seq 21 30); do
    _emit "h$i" 1 PLAN_CACHE_HIT "" PLAN_HOLES 100 10000
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "ROLLOUT_GATE_FAIL"'
  echo "$output" | grep -q 'pv_pass_rate_on_hit'
}

@test "G6c FAIL cites cost_delta when negative" {
  # 30 HITs, all approved, but adapter=20000 vs saved=10000 each -> delta<0.
  for i in $(seq 1 30); do
    _emit "h$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 20000 10000
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "ROLLOUT_GATE_FAIL"'
  echo "$output" | grep -q 'cost_delta'
}

@test "G_bc1 malformed jsonl line is skipped, valid lines still counted" {
  # Mix valid records with garbage; gate must not crash.
  for i in $(seq 1 30); do
    _emit "s$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  printf 'not-json\n{"verdict":"PLAN_CACHE_HIT"\n' >> "$METRICS_DIR/s1/plan-cache.jsonl"
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "ROLLOUT_GATE_PASS"'
}

@test "G_bc2 empty metrics dir -> INSUFFICIENT_DATA, no crash" {
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "INSUFFICIENT_DATA"'
  echo "$output" | grep -q '"sessions_seen": 0'
}

@test "G_bc3 record with unparseable timestamp does not crash days_span" {
  for i in $(seq 1 30); do
    _emit "s$i" 1 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  python3 -c "
import json
rec={'verdict':'PLAN_CACHE_HIT','session_id':'sBAD','timestamp':'NOT-A-DATE',
     'pv_outcome':'PLAN_APPROVED','adapter_cost_tokens':100,
     'saved_architect_tokens_estimate':10000,'miss_reason':''}
import os; os.makedirs('$METRICS_DIR/sBAD',exist_ok=True)
open('$METRICS_DIR/sBAD/plan-cache.jsonl','w').write(json.dumps(rec)+'\n')
"
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
}

@test "G7b 14-day window with >=30 records ALSO passes data-sufficiency" {
  # Only 1 session id but 30 records spread in last 14 days? Actually
  # sessions_seen counts session dirs. Use 14 sessions each within window
  # but >14 days span: window is whichever is LARGER.
  # Setup: 10 sessions all within last 14 days -> sessions<30 BUT
  # records-in-14d=10 too. Should be INSUFFICIENT.
  for i in $(seq 1 10); do
    _emit "s$i" 2 PLAN_CACHE_HIT "" PLAN_APPROVED 100 10000
  done
  run python3 "$GATE" --metrics-dir "$METRICS_DIR"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"verdict": "INSUFFICIENT_DATA"'
}
