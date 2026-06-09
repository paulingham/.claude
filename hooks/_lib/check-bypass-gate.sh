#!/usr/bin/env bash
# check-bypass-gate — pure bypass-flag detector helper (no side effects).
#
# Source this file to define check_bypass_gate. The function is PURE: it only
# returns 0 or 1 based on the named variable's value. It does NOT exit, does NOT
# write stdout, does NOT log, and does NOT source harness-paths.sh.
# The caller decides what to do with the verdict (exit 0, set a var, etc.).
#
# Modelled on the precedent established by hooks/_lib/session-id.sh:
#   one sourced function, zero side effects, single clear contract.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
#   check_bypass_gate "CLAUDE_DISABLE_SOMETHING" && exit 0
#
# Contract:
#   check_bypass_gate <ENV_VAR_NAME>
#     Returns 0 (bypass active)   when ${!ENV_VAR_NAME} == "1"
#     Returns 1 (bypass inactive) otherwise (unset, empty, "0", "true", etc.)
#
# The indirect expansion ${!1:-0} preserves the exact :-0 default and == "1"
# equality semantics used by every inline bypass check it replaces.

# check_bypass_gate <ENV_VAR_NAME>
#   ENV_VAR_NAME: the name of the environment variable to test (passed by name,
#                 not by value). Uses indirect expansion to read the variable.
check_bypass_gate() {
  [[ "${!1:-0}" == "1" ]]
}
