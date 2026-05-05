#!/usr/bin/env bash
# Cost feed — SubagentStop hook.
# Captures per-spawn token usage to ~/.claude/metrics/costs.jsonl for
# /eval-model-effectiveness analysis. Fail-open on every error path (exit 0).
# POSIX O_APPEND is atomic for records <4096B (~250B per record here).
# Field path verified from subagent-stop-trajectory.sh: top-level .subagent_type.
#
# enforces: rules/_detail/operational-protocol.md:Complexity Budget
# protects: pipeline

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/cost-helpers.sh" 2>/dev/null || exit 0

INPUT=$(cat 2>/dev/null) || exit 0
[ -z "$INPUT" ] && exit 0
echo "$INPUT" | jq -e . >/dev/null 2>&1 || exit 0
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

I_TOK=$(_cf_token "$INPUT" "input_tokens")
O_TOK=$(_cf_token "$INPUT" "output_tokens")
C_TOK=$(_cf_token "$INPUT" "cache_read_input_tokens")
[ "$I_TOK" -eq 0 ] && [ "$O_TOK" -eq 0 ] && [ "$C_TOK" -eq 0 ] && exit 0

AGENT_ROLE=$(_cf_resolve_field "$INPUT" '.subagent_type // .agent_role' "${CLAUDE_SUBAGENT_TYPE:-unknown}")
MODEL=$(_cf_resolve_field "$INPUT" '.model' "${CLAUDE_SUBAGENT_MODEL:-unknown}")
PIPELINE_ID=$(_cf_pipeline_id)
SESSION_ID=$(_cf_session_id)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COST=$(_cf_compute_cost "$I_TOK" "$O_TOK" "$C_TOK")
[ -z "$COST" ] && exit 0

METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR" 2>/dev/null || exit 0

jq -nc \
  --arg ts "$TIMESTAMP" --arg sid "$SESSION_ID" --arg pid "$PIPELINE_ID" \
  --arg role "$AGENT_ROLE" --arg model "$MODEL" \
  --argjson cost "$COST" --argjson i "$I_TOK" --argjson o "$O_TOK" --argjson c "$C_TOK" \
  '{timestamp:$ts,session_id:$sid,pipeline_id:$pid,agent_role:$role,model:$model,total_cost_usd:$cost,input_tokens:$i,output_tokens:$o,cached_tokens:$c,rate_version:"opus-4-7-2026-04"}' \
  >> "$METRICS_DIR/costs.jsonl" 2>/dev/null || true

exit 0
