#!/usr/bin/env bash
# Story 4 tests: backfill CLI, oracle detection, promote, slug generation.
# Uses a gh shim and fixture PRs — no real gh calls.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CAP="$ROOT/skills/internal-eval/capture"
TESTS="$ROOT/skills/internal-eval/tests"
PASS=0; FAIL=0

source "$TESTS/_lib/assert.sh"
source "$TESTS/_lib/backfill_checks.sh"

check_oracle_paths   "$CAP"
check_privacy_banner "$CAP" "$ROOT"
check_oracle_match   "$CAP" "$TESTS"
check_oracle_exclude "$CAP"
check_slug           "$CAP"
check_promote        "$CAP" "$ROOT"
check_pr_to_case     "$CAP" "$TESTS"
check_skill_md       "$ROOT"

echo "# pass=$PASS fail=$FAIL"; [ "$FAIL" -eq 0 ]
