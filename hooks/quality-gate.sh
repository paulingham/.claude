#!/usr/bin/env bash
# Quality Gate Hook — PreToolUse on "gh pr create"
# Refactored: per-check logic extracted to _lib/quality-gate-checks.sh
# (instinct: file >44 lines requires _lib/ extraction before adding new logic)
#
# enforces: protocols/pipeline-protocol.md:Phase Checklist
# protects: pr-creation, code-review
# self-test: skip

source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[[ "$TOOL_NAME" != "Bash" || ! "$COMMAND" =~ "gh pr create" ]] && exit 0

echo "QUALITY GATE: Running pre-PR checks..." >&2
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/quality-gate-checks.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/quality-gate-pairing.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/jsonl-emit.sh"

# Log-only advisory when CLAUDE_PIPELINE_TASK_ID is empty (logic in _lib).
_qg_taskid_advisory

RT=$(_qg_detect_runtime)
ANY_FAILED=0
# CLAUDE_QG_SKIP_CHECKS=1 skips the heavy checks (tests/lint/audit/shape/
# contract) while preserving advisory + freshness logic; set by the test
# conftest so a test invoking this hook does NOT recursively re-run the suite.
#
# WHY: this check loop MUST stay identical to
# skills/pr-creation/lib/check-quality-gate.sh (the skill-step mirror of this
# hook). If you add a new check here, add it there too — the skill step is the
# path-independent gate for gh api / MCP PR creation. GP-C1, issue #33106.
if [[ "${CLAUDE_QG_SKIP_CHECKS:-0}" != "1" ]]; then
  for check in tests lint audit shape contract; do
    _qg_check_${check} "$RT"; rc=$?
    [[ $rc -ne 0 ]] && ANY_FAILED=1
  done
fi
_qg_check_freshness "$COMMAND"; rc=$?
[[ $rc -ne 0 ]] && ANY_FAILED=1

_qg_finalize "$ANY_FAILED"
exit $?
