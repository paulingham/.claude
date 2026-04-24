#!/usr/bin/env bash
# Story 8 — oracle scoring modes + flakiness retry.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="$ROOT/skills/internal-eval/run"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/scoring_checks.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/scoring_mode_emit_checks.sh"

check_exact_mode_pass "$RUN"
check_exact_mode_fail "$RUN"
check_normalized_mode "$RUN"
check_test_passing_mode "$RUN"
check_score_dispatch_gate_fail "$RUN"
check_score_dispatch_exact_pass "$RUN"
check_score_dispatch_exact_fail "$RUN"
check_retry_deterministic_no_retry "$RUN"
check_retry_2x_passes_second "$RUN"
check_retry_2x_all_fail "$RUN"
check_retry_quarantined_runs_once "$RUN"
check_result_json_has_attempts "$RUN"
check_emit_status_forwards_attempts "$RUN"
check_emit_status_scoring_modes "$RUN"
check_runner_threads_scoring_mode "$RUN"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
