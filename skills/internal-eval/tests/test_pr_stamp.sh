#!/usr/bin/env bash
# Story 9 — PR body eval-baseline stamp.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCORE="$ROOT/skills/internal-eval/score"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/stamp_checks.sh"

_eq() { [ "$1" = "$2" ]; }

check_stamp_stub_when_no_baseline "$SCORE"
check_stamp_emits_section_with_baseline "$SCORE"
check_stamp_has_harness_ref_timestamp_date "$SCORE"
check_stamp_baseline_file_link "$SCORE"
check_stamp_methodology_disclaimer "$SCORE"
check_stamp_missing_field_graceful "$SCORE"
check_stamp_honours_model_arg "$SCORE"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
