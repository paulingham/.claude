#!/usr/bin/env bash
# Quality Gate Hook — PreToolUse on "gh pr create"
# Refactored: per-check logic extracted to _lib/quality-gate-checks.sh
# (instinct: file >44 lines requires _lib/ extraction before adding new logic)
#
# enforces: protocols/pipeline-protocol.md:Phase Checklist
# protects: pr-creation, code-review
# self-test: skip

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

# Log-only advisory: empty CLAUDE_PIPELINE_TASK_ID corrupts cross-pipeline
# state via the pipeline-state/unknown/ fallback at line 37 below. Emit a
# would-block event + actionable stderr; promote to exit 2 after 14d soak
# (see plan: fix-freshness-gate-fallback-corruption slice A).
if [[ -z "${CLAUDE_PIPELINE_TASK_ID:-}" ]]; then
  ADV_EVENTS=$(_qg_events_path)
  mkdir -p "$(dirname "$ADV_EVENTS")"
  _jsonl_emit "$ADV_EVENTS" source would-block-task-id task_id ""
  cat >&2 <<'ADVISORY'
ADVISORY: quality-gate freshness check requires CLAUDE_PIPELINE_TASK_ID to be set.
Empty value triggers cross-pipeline state corruption via pipeline-state/unknown/.

Fix options:
  1. Set CLAUDE_PIPELINE_TASK_ID=<task-id> in your shell, OR
  2. Re-run via /pipeline (Step 2c sets it automatically), OR
  3. Refresh the stale stub yourself:
     echo "{\"task_id\":\"unknown\",\"verdict\":\"VERIFIED\",\"git_head\":\"$(git rev-parse HEAD)\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"branch\":\"main\"}" > ~/.claude/pipeline-state/unknown/verification-evidence.json

Soak: log-only for 14d (see feedback_freshness_gate_no_t1_carveout.md).
ADVISORY
fi

RT=$(_qg_detect_runtime)
ANY_FAILED=0
for check in tests lint audit shape contract; do
  _qg_check_${check} "$RT"
  rc=$?
  [[ $rc -ne 0 ]] && ANY_FAILED=1
done
_qg_check_freshness "$COMMAND"
rc=$?
[[ $rc -ne 0 ]] && ANY_FAILED=1

TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-unknown}"
EVENTS=$(_qg_events_path)
mkdir -p "$(dirname "$EVENTS")"
if [[ $ANY_FAILED -eq 0 ]]; then
  _qg_write_snapshot "$TASK_ID"
  _jsonl_emit "$EVENTS" source passed task_id "$TASK_ID"
  echo "QUALITY GATE PASSED" >&2
  exit 0
else
  _jsonl_emit "$EVENTS" source prevented task_id "$TASK_ID"
  echo "QUALITY GATE FAILED: Fix issues before creating PR" >&2
  exit 2
fi
