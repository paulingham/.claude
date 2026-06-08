#!/usr/bin/env bash
# Append a JSON line to ~/.claude/metrics/{session}/<jsonl_filename>.
# Usage: log-injection.sh <input-json> <resolved-json> <source> [jsonl_filename]
#
# INPUT (the raw Agent tool payload) may be passed as $1 OR, when $1 is empty,
# read from STDIN. The stdin form avoids ARG_MAX: a pathological subagent_type
# (e.g. the 1M-char capping test) exceeds the per-arg limit on Linux and
# silently fails the exec, dropping the log line (macOS's larger ARG_MAX masks
# this). Callers with bounded input keep using $1; callers that may pass huge
# input pipe it and pass "" as $1.
# jsonl_filename defaults to hook-injections.jsonl (thinking-defaults caller).
# Source is "logged" (Path B advisory, current), "blocked" (Path B enforcement,
# future), or "injected" (Path A, future).
# Sanitises CLAUDE_SESSION_ID against path traversal; caps agent_role at 64 chars.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
INPUT="$1"
RESOLVED="$2"
SOURCE="$3"
FILENAME="${4:-hook-injections.jsonl}"
# When INPUT was not passed as an argument, read it from stdin (ARG_MAX-safe).
[[ -z "$INPUT" ]] && INPUT="$(cat)"
SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HARNESS_DATA/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# INPUT goes to the inner python via stdin too (it can be huge); TS/SOURCE/
# RESOLVED are small + bounded, so they stay on argv. agent_role is capped at
# 64 chars. RESOLVED defaults to {} when empty/invalid.
printf '%s' "$INPUT" | python3 -c "import json,sys
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
