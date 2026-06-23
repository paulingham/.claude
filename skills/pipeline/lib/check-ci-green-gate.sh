#!/usr/bin/env bash
# check-ci-green-gate.sh — Enforcing CI-green gate at Ship→Deploy entry.
# Exit 0 = ALLOW (CI conclusively green), Exit 2 = BLOCK (CI not green).
#
# Called from skills/pipeline/SKILL.md Step 5 BEFORE /harness:deploy auto-invoke.
# Mirrors skills/pr-creation/lib/check-quality-gate.sh structure.
#
# C4: Operator escape — CLAUDE_CI_GREEN_GATE=off → exit 0 with loud warning.
# WHY: escape is checked at the TOP before sourcing the reader, so the reader's
# fail-closed path is never consulted when the escape is active. The escape is
# deliberately separate from the reader's unevaluable-input path.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve PR number from argument — BLOCK if empty/absent.
# WHY: cd "" rc=0 (QG-gate-wrapper-test-traps memory); guard before use.
_ccgg_resolve_pr() {
  printf '%s' "${1:-}"
}

PR="$(_ccgg_resolve_pr "${1:-}")"

# C4: Honour operator escape BEFORE sourcing reader.
# WHY: the escape must NOT interact with the reader's fail-closed paths —
# it exits here, before the reader is even loaded. Documented in
# protocols/agent-protocol.md § Reversibility Escapes.
if [[ "${CLAUDE_CI_GREEN_GATE:-}" == "off" ]]; then
  echo "WARNING: CLAUDE_CI_GREEN_GATE=off — CI-green gate skipped for PR #${PR:-<unknown>}. Fix CI before deploying to production." >&2
  echo "[ci-green-gate] Gate bypassed via CLAUDE_CI_GREEN_GATE=off override for PR #${PR:-<unknown>}."
  exit 0
fi

# Guard: BLOCK if PR arg is empty (before sourcing reader).
if [[ -z "$PR" ]]; then
  echo "CI_RED — deploy halted: no PR number provided to CI-green gate." >&2
  echo "Fix: pass the PR number as the first argument to check-ci-green-gate.sh." >&2
  echo "Override (deliberate only): CLAUDE_CI_GREEN_GATE=off" >&2
  exit 2
fi

# Source the fail-closed reader.
# shellcheck source=/dev/null
source "$SCRIPT_DIR/../../../hooks/_lib/ci-status-reader.sh"

# Invoke the reader — it sets _CSR_REASON on BLOCK.
ci_status_decision "$PR"
GATE_RC=$?

_ccgg_emit_verdict() {
  local rc="$1" pr="$2" reason="${3:-unknown}"
  if [[ $rc -eq 0 ]]; then
    echo "CI_GREEN — CI is conclusively green for PR #${pr}. Proceeding to Deploy."
    return 0
  fi
  # C4b: human-readable block message naming PR#, observed reason, and override hint.
  echo "CI_RED — deploy halted: CI is not conclusively green for PR #${pr} (observed: ${reason})." >&2
  echo "Fix the failing checks and re-run, or deliberately override with CLAUDE_CI_GREEN_GATE=off (logged)." >&2
  echo ""
  echo "CI_RED — deploy halted for PR #${pr} (${reason}). Re-enter fix loop."
  return 2
}

_ccgg_emit_verdict "$GATE_RC" "$PR" "${_CSR_REASON:-unknown}"
exit $?
