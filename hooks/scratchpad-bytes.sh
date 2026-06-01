#!/usr/bin/env bash
# Pre-Agent Scratchpad Bytes — PreToolUse hook for Agent matcher.
# Measures the bytes of the post-filter scratchpad section embedded in the
# spawn prompt and logs to ~/.claude/metrics/{session}/scratchpad-bytes.jsonl
# for forensic visibility on injection size. Read-only; never blocks.
#
# enforces: protocols/autonomous-intelligence.md:Pipeline Scratchpad
# protects: pipeline, learn

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

[[ "${CLAUDE_DISABLE_SCRATCHPAD_BYTES:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
RESOLVED=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/scratchpad-bytes.py" 2>/dev/null) || exit 0
[[ -z "$RESOLVED" ]] && exit 0

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
DIR="$HARNESS_DATA/metrics/$SESSION"
mkdir -p "$DIR" 2>/dev/null || exit 0
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c "import json,sys
print(json.dumps({
  'timestamp': sys.argv[1],
  'source': 'scratchpad-bytes',
  'agent_role': json.loads(sys.argv[2]).get('subagent_type',''),
  'task_id': json.loads(sys.argv[2]).get('task_id',''),
  'section_bytes': json.loads(sys.argv[2]).get('section_bytes',0),
  'body_bytes': json.loads(sys.argv[2]).get('body_bytes',0)
}))" "$TS" "$RESOLVED" >> "$DIR/scratchpad-bytes.jsonl" 2>/dev/null
exit 0
