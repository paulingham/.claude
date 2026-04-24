#!/usr/bin/env bash
# Story 7 — suite orchestration tests (run-suite.sh + lib/suite-*.sh).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="$ROOT/skills/internal-eval/run"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/run_suite_checks.sh"

check_suite_args_required "$RUN"
check_suite_args_defaults "$RUN"
check_suite_args_flags "$RUN"
check_resume_detection "$RUN"
check_resume_filter "$RUN"
check_aggregate_counts "$RUN"
check_aggregate_pass_rate "$RUN"
check_aggregate_empty_denominator "$RUN"
check_shared_harness_live "$RUN"
check_shared_harness_pinned "$RUN"
check_pool_runs_all "$RUN"
check_pool_respects_concurrency "$RUN"
check_suite_end_to_end "$RUN"
check_suite_resume_skips "$RUN"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
