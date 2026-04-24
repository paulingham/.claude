#!/usr/bin/env bash
# Story 8 — regression diff tests.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCORE="$ROOT/skills/internal-eval/score"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/regression_checks.sh"

check_regressions_detected "$SCORE"
check_no_regressions_passed "$SCORE"
check_improvements_quadrant "$SCORE"
check_added_removed_neutral "$SCORE"
check_failed_infra_never_regression "$SCORE"
check_failed_timeout_never_regression "$SCORE"
check_regression_md_rendered "$SCORE"
check_intersection_excludes_incompatible "$SCORE"
check_quarantined_excluded "$SCORE"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
