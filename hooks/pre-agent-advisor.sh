#!/usr/bin/env bash
# Pre-Agent Advisor-Mode — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves would-be Sonnet+Opus-advisor pairing for reviewer spawns and logs to
# ~/.claude/metrics/{session}/advisor-dispatch.jsonl. Does NOT block: the Agent
# tool input schema does not currently expose `advisor`, so enforcement is
# deferred until the schema lands. Mirrors pre-agent-thinking.sh shape.
#
# enforces: protocols/thinking-defaults.md:Advisor-Mode Reviews
# protects: code-review, security-review

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

[[ "${CLAUDE_DISABLE_ADVISOR_GATE:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-advisor.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
CLAUDE_SESSION_ID="$SESSION" \
  bash "${HOOK_DIR}/_lib/log-injection.sh" "$INPUT" "$RESOLVED" "logged" "advisor-dispatch.jsonl" 2>/dev/null

# AC8b — patch-critic mode-token mutual-exclusivity guard.
# Classifies the spawn prompt's mode tokens (Mode: tournament vs Persona:).
# Dual-token spawns emit a forensic JSONL line with source "mode-ambiguous"
# and the offending token list. Path-B advisory: never blocks the spawn.
if [[ "$SUBAGENT_TYPE" == "patch-critic" ]]; then
  MODE_OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-mode-token.py" 2>/dev/null) || exit 0
  MODE_DECISION=$(printf '%s\n' "$MODE_OUT" | sed -n '1p')
  MODE_RESOLVED=$(printf '%s\n' "$MODE_OUT" | sed -n '2p')
  if [[ "$MODE_DECISION" == "LOG" ]]; then
    CLAUDE_SESSION_ID="$SESSION" \
      bash "${HOOK_DIR}/_lib/log-injection.sh" "$INPUT" "$MODE_RESOLVED" "mode-ambiguous" "advisor-dispatch.jsonl" 2>/dev/null
  fi
fi

exit 0
