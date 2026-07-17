#!/usr/bin/env bash
# SubagentStart hook: (1) writes agent role to temp file for observation-capture.sh,
# (2) emits hookSpecificOutput.additionalContext injecting gear-aware rules content
# into the SPAWNING subagent's own context.
# Runs in the orchestrator process BEFORE the subagent starts.
# observation-capture.sh reads (1) as fallback when env var is empty.
# For parallel agents: last-writer-wins (acceptable — parallel agents share phase).
#
# Rules injection (2) is safety-critical and MUST run in every hook profile and
# every gear — it is never gated behind check_hook_profile. Only the role-state
# bookkeeping write is profile-gated. safety.md is ALWAYS included; pipeline-
# rigour.md is included unless the gear is affirmatively PAIR — an absent or
# unreadable gear marker fails toward MORE rules (BUILD/PIPELINE), never fewer.
#
# enforces: protocols/agent-protocol.md:Pipeline Scratchpad Protocol
# enforces: rules/safety.md (universal) + rules/pipeline-rigour.md (gear-conditional)
# protects: pipeline

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStart"
trap 'log_hook_event $?' EXIT

# shellcheck source=_lib/state-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
# shellcheck source=_lib/session-id.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/session-id.sh"
_ensure_state_dir

INPUT=$(cat)
AGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.subagent_type // .agent_type // empty' 2>/dev/null)

# Role-state bookkeeping write stays profile-gated (observation-capture.sh's
# use of it is diagnostic, not safety-bearing).
if source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" \
    && check_hook_profile "standard" \
    && [[ -n "$AGENT_TYPE" ]]; then
  printf '%s\n' "$AGENT_TYPE" | _state_write "agent-role-${PPID}" 2>/dev/null || true
fi

_subagent_context_gear() {
  local sid="$1"
  local gear
  gear=$(_state_read "gear-${sid}" 2>/dev/null) || { printf ''; return 0; }
  printf '%s' "${gear//$'\n'/}"
}

_subagent_context_build() {
  local safety_path pipeline_rigour_path context gear sid
  safety_path="$(dirname "${BASH_SOURCE[0]}")/../rules/safety.md"
  pipeline_rigour_path="$(dirname "${BASH_SOURCE[0]}")/../rules/pipeline-rigour.md"

  context=""
  [[ -f "$safety_path" ]] && context=$(cat "$safety_path")

  sid=$(resolve_session_id "$INPUT")
  gear=$(_subagent_context_gear "$sid")
  # Fail toward MORE rules: include pipeline-rigour unless gear is affirmatively PAIR.
  if [[ "$gear" != "PAIR" ]] && [[ -f "$pipeline_rigour_path" ]]; then
    context="${context}

$(cat "$pipeline_rigour_path")"
  fi

  printf '%s' "$context"
}

_subagent_context_to_json() {
  local context="$1"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg ctx "$context" \
      '{hookSpecificOutput: {hookEventName: "SubagentStart", additionalContext: $ctx}}'
    return 0
  fi
  # jq-free degradation: escape for JSON string embedding by hand.
  local escaped="${context//\\/\\\\}"
  escaped="${escaped//\"/\\\"}"
  escaped="${escaped//$'\n'/\\n}"
  printf '{"hookSpecificOutput":{"hookEventName":"SubagentStart","additionalContext":"%s"}}\n' "$escaped"
}

_subagent_context_to_json "$(_subagent_context_build)"

exit 0
