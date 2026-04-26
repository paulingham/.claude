#!/usr/bin/env bash
# Pre-Agent Thinking Defaults — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves the would-be defaults for Agent spawns missing tool_input.thinking and
# logs to ~/.claude/metrics/{session}/hook-injections.jsonl. Does NOT block: the
# Agent tool input schema does not currently expose `thinking`, so enforcement is
# deferred until Claude Code lands modified_tool_input support (Path A).
# See pipeline-state/opus47-thinking-defaults-scratchpad/build-probe.md.

# shellcheck source=/dev/null
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python3 -c 'import json,sys
try: d=json.loads(sys.stdin.read())
except Exception: d={}
print(d.get("tool_name",""))')
[[ "$TOOL_NAME" == "Agent" ]] || exit 0

RESOLVED=$(echo "$INPUT" | python3 ~/.claude/hooks/_lib/resolve-thinking.py 2>/dev/null) || exit 0
MISSING=$(echo "$RESOLVED" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("missing", False))')
[[ "$MISSING" == "True" ]] || exit 0

bash ~/.claude/hooks/_lib/log-injection.sh "$INPUT" "$RESOLVED" "logged" 2>/dev/null
exit 0
