#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_eval_capture_hook.bats
# Story 5 tests: auto-capture on PR merge hook.
# Hermetic — uses mock gh via CLAUDE_EVAL_FIX_DIR / CLAUDE_EVAL_FIXTURE.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOKS="$ROOT/hooks"
TESTS="$ROOT/hooks/tests"
PASS=0; FAIL=0

source "$ROOT/skills/internal-eval/tests/_lib/assert.sh"
source "$TESTS/_lib/eval_capture_checks.sh"

check_hook_exists          "$HOOKS"
check_fast_exit_unacked    "$HOOKS"
check_fast_exit_acked      "$HOOKS"
check_fast_exit_file_acked "$HOOKS"
check_worker_date_filter   "$HOOKS" "$ROOT"
check_worker_oracle_filter "$HOOKS" "$ROOT"
check_worker_happy_path    "$HOOKS" "$ROOT"
check_worker_never_promotes "$HOOKS" "$ROOT"
check_worker_capture_log   "$HOOKS" "$ROOT"
check_worker_capture_log_on_skip "$HOOKS" "$ROOT"
check_settings_registration "$ROOT"
check_skill_md_updated     "$ROOT"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
