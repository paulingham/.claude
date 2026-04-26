#!/usr/bin/env bash
# Test-passing scoring: the oracle is an executable whose exit code is authoritative.
# Defers test selection to the case; this helper just runs it under the candidate
# worktree's environment. rc 0 = pass, non-zero = fail.

# score_test_passing <oracle-runner> [args...] → rc of oracle-runner.
score_test_passing() {
  "$@" >/dev/null 2>&1
}
