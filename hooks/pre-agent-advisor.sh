#!/usr/bin/env bash
# Pre-Agent Advisor-Mode — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves would-be Sonnet+Opus-advisor pairing for reviewer spawns and logs to
# ~/.claude/metrics/{session}/advisor-dispatch.jsonl. Does NOT block: the Agent
# tool input schema does not currently expose `advisor`, so enforcement is
# deferred until the schema lands. Mirrors pre-agent-thinking.sh shape.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-advisor.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0

SESSION="${CLAUDE_SESSION_ID:-local-$$}"
DIR="$HOME/.claude/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import json,sys
print(json.dumps({
  'timestamp': sys.argv[1], 'source': 'logged',
  'agent_role': json.loads(sys.argv[2]).get('tool_input',{}).get('subagent_type',''),
  'resolved': json.loads(sys.argv[3])
}))" "$TS" "$INPUT" "$RESOLVED" >> "$DIR/advisor-dispatch.jsonl" 2>/dev/null
exit 0
