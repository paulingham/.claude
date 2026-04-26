#!/usr/bin/env bash
# Dispatch one case through run-case.sh. Called by suite-pool via a launcher fn.
# Env prerequisites (inherited from run-suite.sh): EVAL_RUNS_DIR, RUN_ID,
# MODEL, HARNESS_REF, EVAL_CASES_DIR, EVAL_INNER_STUB (test only).

# dispatch_case <case-id>
dispatch_case() {
  local case_id="$1"
  local rc_path="$(dirname "${BASH_SOURCE[0]}")/../run-case.sh"
  bash "$rc_path" --case-id "$case_id" --run-id "$RUN_ID" \
    --model "$MODEL" --harness-ref "$HARNESS_REF" >/dev/null 2>&1 || true
}
