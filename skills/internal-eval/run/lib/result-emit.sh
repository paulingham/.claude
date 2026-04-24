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

_emit_result() {
  write_result_json "$1" case="$CASE_ID" run="$RUN_ID" status="$2" \
    duration="$3" cost=0 rounds=0 rework=false harness="$4" model="$MODEL" \
    flakiness=deterministic scoring="$5" attempts="$6" \
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)" inner="$7" reason="$8"
}

emit_status() {
  local att="${7:-1}" mode="${8:-test-passing}"
  _emit_result "$1" "$2" "$5" "$4" "$mode" "$att" "$3" "$6"
}
