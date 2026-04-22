#!/usr/bin/env bash
# Source-once bats helpers shared by every *.bats spec.
# Usage in a spec:   load '../helpers.bash'
# Safe to source from plain bash too (used by the python meta-tests).

cli_assert_ok() {
  "$@"
}

cli_assert_stdout_match() {
  local pattern="$1"; shift
  "$@" | grep -q -- "$pattern"
}
