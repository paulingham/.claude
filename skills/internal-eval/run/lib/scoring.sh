#!/usr/bin/env bash
# Strict-binary per-case scoring. Story 6 ships the STATUS ENUM plumbing only;
# Story 8 extends score_case with oracle-test execution for scoring_mode=test-passing.
#
# A case `passed` only if ALL inner gates green. Anything else → `failed_diff`.
# Inner pipeline errors map to `failed_build`; those are scored by the runner,
# not here (this fn only interprets gate verdicts).

# score_case <code-review> <security-review> <verify> <qa> <accept>
# → echoes "passed" or "failed_diff"
score_case() {
  _all_green "APPROVE" "$1" "$2" && _all_green "VERIFIED" "$3" \
    && _all_green "COVERED" "$4" && _all_green "APPROVED" "$5" \
    && { echo "passed"; return; }
  echo "failed_diff"
}

# _all_green <expected> <verdict>...  -- every verdict must equal expected.
_all_green() {
  local expected="$1"; shift
  for v in "$@"; do [ "$v" = "$expected" ] || return 1; done
}
