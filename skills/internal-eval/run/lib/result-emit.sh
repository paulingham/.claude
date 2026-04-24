#!/usr/bin/env bash
# Status-code mapping + result.json emitter. Split from runner.sh to respect
# the 50-line-per-file shell shape budget.

rc_to_status() {
  case "$1" in 0) echo passed ;; 124) echo failed_timeout ;;
    2) echo failed_infra ;; *) echo failed_build ;;
  esac
}

rc_reason() {
  case "$1" in 0) echo "" ;; 124) echo "wall-clock timeout exceeded" ;;
    2) echo "harness infra failure" ;; *) echo "inner pipeline exit=$1" ;;
  esac
}

emit_status() {
  local out="$1"; local status="$2"; local inner="$3"; local sha="$4"
  local duration="$5"; local reason="$6"
  write_result_json "$out" case="$CASE_ID" run="$RUN_ID" status="$status" \
    duration="$duration" cost=0 rounds=0 rework=false harness="$sha" model="$MODEL" \
    flakiness=deterministic scoring=test-passing \
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)" inner="$inner" reason="$reason"
}
