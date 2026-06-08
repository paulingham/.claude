#!/usr/bin/env bash
# Append a JSON line to ~/.claude/metrics/{session}/<jsonl_filename>.
# Usage: printf '%s' "$INPUT" | log-injection.sh <resolved-json> <source> [jsonl_filename]
#
# INPUT (the raw Agent tool payload) is read from STDIN, NOT argv: a pathological
# subagent_type (e.g. the 1M-char capping test) exceeds ARG_MAX on Linux and
# silently fails the exec, dropping the log line — and macOS's larger ARG_MAX
# masks it. RESOLVED/SOURCE/FILENAME are small + bounded, so they stay on argv.
# jsonl_filename defaults to hook-injections.jsonl (thinking-defaults caller).
# Source is "logged" (Path B advisory, current), "blocked" (Path B enforcement,
# future), or "injected" (Path A, future).
# Sanitises CLAUDE_SESSION_ID against path traversal; caps agent_role at 64 chars.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
RESOLVED="$1"
SOURCE="$2"
FILENAME="${3:-hook-injections.jsonl}"
SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HARNESS_DATA/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import json,sys
ts, source, raw_resolved = sys.argv[1], sys.argv[2], sys.argv[3]
raw_input = sys.stdin.read()
try:
    resolved = json.loads(raw_resolved) if raw_resolved.strip() else {}
except (ValueError, TypeError):
    resolved = {}
print(json.dumps({
  'timestamp': ts, 'source': source,
  'agent_role': json.loads(raw_input).get('tool_input',{}).get('subagent_type','')[:64],
  'resolved': resolved
}))" "$TS" "$SOURCE" "$RESOLVED" >> "$DIR/$FILENAME" 2>/dev/null
