#!/usr/bin/env bash
# Append a JSON line to ~/.claude/metrics/{session}/hook-injections.jsonl
# Usage: log-injection.sh <input-json> <resolved-json> <source>
# Source is "blocked" (Path B refusal) or "injected" (Path A success, future).

INPUT="$1"
RESOLVED="$2"
SOURCE="$3"
SESSION="${CLAUDE_SESSION_ID:-local-$$}"
DIR="$HOME/.claude/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import json,sys
print(json.dumps({
  'timestamp': sys.argv[1], 'source': sys.argv[2],
  'agent_role': json.loads(sys.argv[3]).get('tool_input',{}).get('subagent_type',''),
  'resolved': json.loads(sys.argv[4])
}))" "$TS" "$SOURCE" "$INPUT" "$RESOLVED" >> "$DIR/hook-injections.jsonl" 2>/dev/null
