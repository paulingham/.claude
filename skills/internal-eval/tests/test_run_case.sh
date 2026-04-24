#!/usr/bin/env bash
# Story 6 — single-case runner tests (run-case.sh + lib/*).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="$ROOT/skills/internal-eval/run"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/run_case_checks.sh"

check_status_enum "$RUN"
check_result_writer "$RUN"
check_isolation_env "$RUN"
check_isolation_paths "$RUN"
check_harness_ref "$RUN"
check_harness_ref_pinned "$RUN"
check_harness_ref_failure "$RUN"
check_scoring_stub "$RUN"
check_timeout "$RUN"
check_dry_run "$ROOT" "$RUN"
check_run_case_keys "$ROOT" "$RUN"
check_inner_state_location "$ROOT" "$RUN"
check_kill_midrun_cleanliness "$ROOT" "$RUN"
check_timeout_status "$ROOT" "$RUN"
check_pass_status "$ROOT" "$RUN"
check_infra_failure "$ROOT" "$RUN"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
