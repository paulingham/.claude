#!/usr/bin/env bash
# Story 8 — baseline capture tests.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCORE="$ROOT/skills/internal-eval/score"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/baseline_checks.sh"

check_baseline_writer_frontmatter "$SCORE"
check_baseline_per_case_table "$SCORE"
check_capture_baseline_writes_file "$SCORE"
check_capture_baseline_symlink_updates "$SCORE"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
