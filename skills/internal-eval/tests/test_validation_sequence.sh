#!/usr/bin/env bash
# Story 11 — validation sequence tests. Proves stub, seed, phase runners, and
# the top-level run-validation-sequence.sh catch injected regressions.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VAL="$ROOT/skills/internal-eval/validate"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/validation_checks.sh"

check_stub_reads_manifest_pass "$VAL"
check_stub_reads_manifest_fail "$VAL"
check_stub_default_pass "$VAL"
check_seed_creates_three_cases "$VAL"
check_seed_deterministic_tier "$VAL"
check_assert_pass_rate_equals "$VAL"
check_assert_verdict "$VAL"
check_assert_regression_count_ge "$VAL"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
