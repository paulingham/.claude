#!/usr/bin/env bash
# Strict-binary per-case scoring. A case `passed` iff ALL gates green AND the
# oracle check for the case's scoring_mode passes. Any gate failure routes to
# `failed_diff`; oracle failure also routes to `failed_diff` (Story 8).

_scoring_dir="$(dirname "${BASH_SOURCE[0]}")/scoring-modes"
# shellcheck source=scoring-modes/exact.sh
source "$_scoring_dir/exact.sh"
# shellcheck source=scoring-modes/normalized.sh
source "$_scoring_dir/normalized.sh"
# shellcheck source=scoring-modes/test-passing.sh
source "$_scoring_dir/test-passing.sh"

# score_case_full <review> <sec> <verify> <qa> <accept> <mode> <a> <b>
#   mode=exact|normalized → a=golden, b=candidate diff paths
#   mode=test-passing     → a=oracle runner, b=unused (pass "::")
# Echoes "passed" or "failed_diff".
score_case_full() {
  _gates_green "$1" "$2" "$3" "$4" "$5" || { echo failed_diff; return; }
  _run_oracle "$6" "$7" "$8" && { echo passed; return; }
  echo failed_diff
}

# Legacy 5-arg signature (Story 6 callers); mode-less → passes when gates green.
score_case() {
  _gates_green "$@" && { echo passed; return; }
  echo failed_diff
}

_gates_green() {
  [ "$1" = APPROVE ] && [ "$2" = APPROVE ] && [ "$3" = VERIFIED ] \
    && [ "$4" = COVERED ] && [ "$5" = APPROVED ]
}

_run_oracle() {
  case "$1" in
    exact)         score_exact "$2" "$3" ;;
    normalized)    score_normalized "$2" "$3" ;;
    test-passing)  score_test_passing "$2" ;;
    *)             return 1 ;;
  esac
}
