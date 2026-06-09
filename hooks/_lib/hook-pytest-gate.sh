#!/usr/bin/env bash
# hook-pytest-gate.sh — reusable predicate + runner for the hook-change pytest gate.
#
# CWD MUST be the worktree — a repo-root run tests unchanged main and false-passes
# (GP-19). See AC1 test.
#
# diff base is main...HEAD (NOT HEAD~1) — HEAD~1 misses hook changes in earlier commits.
#
# Three exported functions:
#   _hpg_hook_body_changed <worktree>  — returns 0 if gate should fire
#   _hpg_targeted_nodes    <worktree>  — echoes the targeted test-file subset
#   _hpg_run               <worktree>  — runs pytest subset, returns non-zero on red
#
# Honour: check_bypass_gate "CLAUDE_DISABLE_HOOK_PYTEST_GATE"
#         CLAUDE_HOOK_PYTEST_GATE_FULL=1 opt-in (runs full suite with -k '' scope-flag)
#
# bash-3.2 clean; no set -e (explicit returns/exits only).
# if this regresses to a gh-keyed hook, gh api bypasses it — see GP-19.

# Source check-bypass-gate (pure, no side effects).
# shellcheck source=/dev/null
_HPG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_HPG_DIR/check-bypass-gate.sh"

# ---------------------------------------------------------------------------
# _hpg_hook_body_changed <worktree>
#
# Returns 0 (fire) if git diff --name-only main...HEAD in <worktree> matches
# ^hooks/([^/]*|_lib/[^/]*)\.sh$ AND those files' unified diff has ≥1
# added/removed non-blank line.
# On diff-command error → FIRE conservatively (returns 0).
# Returns 1 (no-op) otherwise.
# ---------------------------------------------------------------------------
_hpg_hook_body_changed() {
  local wt="${1:-$(pwd)}"

  # Get all changed files via main...HEAD (three-dot — catches all branch commits).
  local all_changed rc_diff
  all_changed=$(git -C "$wt" diff --name-only "main...HEAD" 2>/dev/null)
  rc_diff=$?
  if [ "$rc_diff" -ne 0 ]; then
    echo "[hpg] WARN: git diff failed (rc=$rc_diff); firing gate conservatively." >&2
    return 0
  fi

  # Filter to hook files only (top-level hooks/*.sh and hooks/_lib/*.sh).
  local changed_hooks
  changed_hooks=$(printf '%s\n' "$all_changed" \
    | grep -E '^hooks/([^/]*|_lib/[^/]*)\.sh$' || true)

  # No hook files changed → no-op.
  if [ -z "$changed_hooks" ]; then
    return 1
  fi

  # Check for ≥1 added/removed non-blank line in the unified diff.
  # Pass hook files as separate args via eval-safe word-splitting on newlines.
  local diff_out rc_udiff hook_args
  # Convert newline-separated list to space-separated for passing to git.
  # shellcheck disable=SC2086
  hook_args=$(printf '%s\n' "$changed_hooks" | tr '\n' '\0' | xargs -0 printf '%s ')
  # shellcheck disable=SC2086
  diff_out=$(git -C "$wt" diff "main...HEAD" -- $hook_args 2>/dev/null)
  rc_udiff=$?
  if [ "$rc_udiff" -ne 0 ]; then
    echo "[hpg] WARN: git diff (unified) failed (rc=$rc_udiff); firing gate conservatively." >&2
    return 0
  fi

  # Extract +/- lines, exclude diff headers (+++/---), check for non-blank content.
  local non_blank
  non_blank=$(printf '%s\n' "$diff_out" \
    | grep -E '^[+-]' \
    | grep -vE '^(\+\+\+|---)' \
    | grep -E '^[+-][[:space:]]*[^[:space:]]') || true

  if [ -z "$non_blank" ]; then
    return 1
  fi

  return 0
}

# ---------------------------------------------------------------------------
# _hpg_targeted_nodes <worktree>
#
# Echoes the subset of test files to run:
#   tests/test_*_invariants.py  UNION  grep -lE 'hooks/' tests/test_*.py
#
# If both resolve empty while a hook changed, emits a loud WARN (not silent pass).
# ---------------------------------------------------------------------------
_hpg_targeted_nodes() {
  local wt="${1:-$(pwd)}"

  local invariants hook_tests
  invariants=$(find "$wt/tests" -maxdepth 1 -name 'test_*_invariants.py' 2>/dev/null | sort || true)
  hook_tests=$(grep -lE 'hooks/' "$wt"/tests/test_*.py 2>/dev/null | sort || true)

  local subset
  subset=$(printf '%s\n%s\n' "$invariants" "$hook_tests" | grep -v '^$' | sort -u) || true

  if [ -z "$subset" ]; then
    echo "[hpg] WARN: no targeted test nodes found while a hook body changed — check test layout." >&2
    return 0
  fi

  printf '%s\n' "$subset"
}

# ---------------------------------------------------------------------------
# _hpg_run <worktree>
#
# Runs pytest <subset> -q -p no:cacheprovider from $wt.
# ANY red ⇒ return non-zero.
# Honour CLAUDE_HOOK_PYTEST_GATE_FULL=1: runs full suite with -k '' scope-flag.
# ---------------------------------------------------------------------------
_hpg_run() {
  local wt="${1:-$(pwd)}"

  # Full-suite opt-in: -k '' satisfies pytest-suite-guard _psg_has_scope_flag.
  if [[ "${CLAUDE_HOOK_PYTEST_GATE_FULL:-0}" == "1" ]]; then
    echo "[hpg] CLAUDE_HOOK_PYTEST_GATE_FULL=1 — running full suite (best-effort, flake-tolerant)." >&2
    (cd "$wt" && pytest tests/ -q -p no:cacheprovider -k '')
    return $?
  fi

  local nodes
  nodes=$(_hpg_targeted_nodes "$wt")

  if [ -z "$nodes" ]; then
    echo "[hpg] WARN: empty targeted subset; skipping pytest run." >&2
    return 0
  fi

  # Run pytest with file-scoped subset (satisfies pytest-suite-guard RULE 1).
  # shellcheck disable=SC2086
  (cd "$wt" && pytest $nodes -q -p no:cacheprovider)
  return $?
}
