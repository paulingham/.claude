#!/usr/bin/env bash
# Pre-Agent Instinct Injection — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves which learned-instincts apply to the spawning agent and logs the
# decision to ~/.claude/metrics/{session}/instinct-injections.jsonl. Does NOT
# block: the Agent tool input schema does not currently expose a way to inject
# prompt content from a hook, so the orchestrator-side caller is responsible
# for the actual prompt-string splice. Mirrors pre-agent-thinking.sh shape.
#
# DO NOT FLIP TO EXIT 2:
#   Unlike pre-agent-allowlist.sh (flipped 2026-05-14), this hook is
#   mutation-only — its value-add is splicing a `## Learned Patterns` block
#   into the prompt, NOT denying a spawn. There is no DECISION branch in
#   the shell layer (the resolver runs unconditionally; see line below),
#   and the delivery path is orchestrator-side splice, not the Agent
#   matcher. Promoting this to exit 2 would refuse every legitimate
#   spawn that the orchestrator should be enriching with instincts.
#   See learning/instincts/hook-enforcement-semantics.md for the
#   pure-deny vs mutation-semantic split.
#
# enforces: protocols/autonomous-intelligence.md:Instinct Injection
# protects: learn, build-implementation

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/check-bypass-gate.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

check_bypass_gate "CLAUDE_DISABLE_INSTINCT_INJECTION" && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-instincts.py" 2>/dev/null
exit 0
