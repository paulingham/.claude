#!/usr/bin/env bash
# Agentic Security Gate — PreToolUse:Agent hook.
# Requires the Agentic OWASP Top 10 checklist (memory poisoning, instinct
# poisoning, tool misuse, goal hijacking) whenever a security-engineer agent is
# spawned over a diff touching learning/, agent-memory/, or hooks/.
# Hard-blocks (exit 2) the spawn when an agentic surface is touched but the
# spawn prompt omits the agentic directive. Bypass: CLAUDE_DISABLE_AGENTIC_GATE=1.
#
# enforces: skills/security-review/SKILL.md § Agentic Surface Gate
# protects: security-review

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "Agent" ]] || exit 0

DECISION=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/agentic_security_gate_cli.py" 2>/dev/null) || exit 0
ACTION=$(printf '%s\n' "$DECISION" | sed -n '1p')
REASON=$(printf '%s\n' "$DECISION" | sed -n '2p')

case "$ACTION" in
  block)
    echo "BLOCKED: $REASON. Add the Agentic OWASP Top 10 directive to the security-engineer spawn prompt (see skills/security-review/SKILL.md § Agentic Surface Gate), or set CLAUDE_DISABLE_AGENTIC_GATE=1 to override." >&2
    exit 2
    ;;
  bypass)
    echo "agentic-security-gate bypassed via CLAUDE_DISABLE_AGENTIC_GATE=1" >&2
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
