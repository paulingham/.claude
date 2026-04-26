#!/usr/bin/env bash
# Append a JSON line to ~/.claude/metrics/{session}/<jsonl_filename>.
# Usage: log-injection.sh <input-json> <resolved-json> <source> [jsonl_filename]
# jsonl_filename defaults to hook-injections.jsonl (thinking-defaults caller).
# Source is "logged" (Path B advisory, current), "blocked" (Path B enforcement, future), or "injected" (Path A, future).
# Sanitises CLAUDE_SESSION_ID against path traversal; caps agent_role at 64 chars.

INPUT="$1"
RESOLVED="$2"
SOURCE="$3"
FILENAME="${4:-hook-injections.jsonl}"
SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HOME/.claude/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import json,sys
print(json.dumps({
  'timestamp': sys.argv[1], 'source': sys.argv[2],
  'agent_role': json.loads(sys.argv[3]).get('tool_input',{}).get('subagent_type','')[:64],
  'resolved': json.loads(sys.argv[4])
}))" "$TS" "$SOURCE" "$INPUT" "$RESOLVED" >> "$DIR/$FILENAME" 2>/dev/null
