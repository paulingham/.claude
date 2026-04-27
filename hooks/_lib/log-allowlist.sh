#!/usr/bin/env bash
# Append a JSON line to ~/.claude/metrics/{session}/tool-allowlist.jsonl.
# Usage: log-allowlist.sh <input-json> <resolved-json> [frontmatter-json]
# Sanitises CLAUDE_SESSION_ID against path traversal; caps agent_role at 64
# chars; field-level caps in log_allowlist_emit keep the line bounded AND
# valid JSON (vs the previous post-serialisation byte slice).

INPUT="$1"
RESOLVED="$2"
FRONTMATTER="${3:-null}"
SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HOME/.claude/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 "$(dirname "$0")/log_allowlist_emit.py" \
  "$TS" "$INPUT" "$RESOLVED" "$DIR/tool-allowlist.jsonl" "$FRONTMATTER"
