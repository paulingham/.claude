#!/usr/bin/env bash
# Story 10 — gate wiring: rules doc + CI workflow stub.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PASS=0; FAIL=0

source "$(dirname "${BASH_SOURCE[0]}")/_lib/assert.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_lib/gate_checks.sh"

check_rules_has_gate_section "$ROOT"
check_rules_lists_trigger_dirs "$ROOT"
check_workflow_file_exists "$ROOT"
check_workflow_yaml_valid "$ROOT"
check_workflow_pr_label_trigger "$ROOT"
check_workflow_invokes_run_suite "$ROOT"
check_workflow_invokes_diff_vs_baseline "$ROOT"
check_workflow_fails_on_non_eval_passed "$ROOT"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
