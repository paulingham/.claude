#!/usr/bin/env bash
# Validates Story 3 first real eval case is authored correctly.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CASE_ID="per-project-instincts-bootstrap-pr19"
C="$ROOT/eval/cases/$CASE_ID"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/checks.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/real_case_checks.sh"

check_artifacts "$C"
check_metadata "$C/metadata.json"
check_real_case "$C"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
