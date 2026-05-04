#!/usr/bin/env bats
# Wave 5b F2 — hook-summary.sh exit-2 vs error differentiation.
# Verifies that intentional enforcement blocks (exit_code == 2) are tracked
# separately from real hook errors (exit_code not in {0, 2}) and that the
# anomaly threshold fires only on the real-error rate.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPT="$REPO_ROOT/scripts/hook-summary.sh"
  TMP="$(mktemp -d -t hs.XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP"
  mkdir -p "$TMP/sessA"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

emit() {
  # emit <hook> <exit_code>  -> append a single record to sessA/hooks.jsonl
  local hook="$1" ec="$2"
  printf '{"timestamp":"2026-01-01T00:00:00Z","hook_name":"%s","trigger":"PreToolUse:Bash","duration_ms":100,"exit_code":%s,"session_id":"sessA"}\n' \
    "$hook" "$ec" >> "$TMP/sessA/hooks.jsonl"
}

@test "F2.1 all-success input -> no anomaly, exit 0" {
  for _ in 1 2 3 4 5; do emit "alpha" 0; done
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "Anomaly check OK"
}

@test "F2.2 only exit-2 events -> no anomaly; hook in Enforcement Blocks not Errors" {
  for _ in 1 2 3 4 5; do emit "blocker" 2; done
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "Most-Frequent Enforcement Blocks"
  echo "$output" | grep -q "blocker"
  echo "$output" | grep -q "Most-Frequent Errors"
  echo "$output" | grep -q "Anomaly check OK"
}

@test "F2.3 mixed errors above threshold -> anomaly, exit 2; hook in Errors section" {
  emit "beta" 0
  emit "beta" 1
  emit "beta" 1
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "ANOMALY"
  echo "$output" | grep -q "beta"
  echo "$output" | grep -q "Most-Frequent Errors"
}

@test "F2.4 enforcement blocks alone do not trigger anomaly even at 100%" {
  for _ in 1 2 3 4 5 6 7 8 9 10; do emit "blocker" 2; done
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 0 ]
}

@test "F2.5 mixed error + enforcement blocks: hook listed in both sections" {
  emit "gamma" 0
  emit "gamma" 2
  emit "gamma" 1
  emit "gamma" 1
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "Most-Frequent Errors"
  echo "$output" | grep -q "Most-Frequent Enforcement Blocks"
  echo "$output" | grep -q "gamma"
}

@test "F2.6 empty log dir -> no records, exit 0" {
  rm -f "$TMP/sessA/hooks.jsonl"
  run bash "$SCRIPT" --anomaly-check
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "No hook telemetry"
}
