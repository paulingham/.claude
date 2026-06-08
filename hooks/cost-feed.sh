#!/usr/bin/env bash
# Cost feed — SubagentStop hook. Hybrid producer: global metrics/costs.jsonl +
# per-session metrics/{sid}/cache.jsonl (for /cache-audit). Fail-open (exit 0).
# Record assembly delegated to _lib/{cache,cost}-jsonl-emit.py so this stays
# ≤50 LOC and cost-helpers.sh stays ≤5-lines-per-function.
# enforces: protocols/operational-protocol.md:Complexity Budget
# protects: pipeline

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
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
[ "$STOP_HOOK_ACTIVE" = "true" ] && { trap - EXIT; exit 0; }  # nested stop: no-op

I_TOK=$(_cf_token "$INPUT" "input_tokens")
O_TOK=$(_cf_token "$INPUT" "output_tokens")
C_TOK=$(_cf_token "$INPUT" "cache_read_input_tokens")
CC_TOK=$(_cf_token "$INPUT" "cache_creation_input_tokens")

AGENT_ROLE=$(_cf_resolve_field "$INPUT" '.subagent_type // .agent_role' "${CLAUDE_SUBAGENT_TYPE:-unknown}")
SESSION_ID=$(_cf_session_id)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
METRICS_DIR="$HARNESS_DATA/metrics"
mkdir -p "$METRICS_DIR" 2>/dev/null || true

# Cache emit runs regardless of token gate (zeros included) so /cache-audit stays fed.
python3 "${HOOK_DIR}/_lib/cache-jsonl-emit.py" "$HARNESS_DATA" "$SESSION_ID" "$TIMESTAMP" "$AGENT_ROLE" "$I_TOK" "$C_TOK" "$CC_TOK" 2>/dev/null || true

# Cost emit requires non-zero tokens (avoids polluting costs.jsonl).
[ "$I_TOK" -eq 0 ] && [ "$O_TOK" -eq 0 ] && [ "$C_TOK" -eq 0 ] && [ "$CC_TOK" -eq 0 ] && exit 0

MODEL=$(_cf_resolve_field "$INPUT" '.model' "${CLAUDE_SUBAGENT_MODEL:-unknown}")
COST=$(_cf_compute_cost "$I_TOK" "$O_TOK" "$C_TOK")
[ -z "$COST" ] && exit 0
python3 "${HOOK_DIR}/_lib/cost-jsonl-emit.py" "$METRICS_DIR" "$TIMESTAMP" "$SESSION_ID" "$(_cf_pipeline_id)" "$AGENT_ROLE" "$MODEL" "$COST" "$I_TOK" "$O_TOK" "$C_TOK" "$(_cf_complexity_budget)" "$(_cf_prior_error_count)" "$(_cf_graph_depth)" "$(_cf_router_decision)" 2>/dev/null || true
exit 0
