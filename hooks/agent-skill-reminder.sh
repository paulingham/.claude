#!/bin/bash
# Agent Skill Reminder — PreToolUse hook for Agent tool
#
# Dual-mode behavior:
#   1. HARD BLOCK (exit 2): Blocks Explore or general-purpose agents spawned
#      with audit/review/compliance keywords. These tasks belong to specialist
#      agents (code-reviewer, security-engineer, qa-engineer) via their skills.
#   2. ADVISORY (exit 0): Reminds the orchestrator to check if a skill should
#      have been invoked before spawning any other agent.
#
# This hook fires BEFORE every Agent spawn. It reads CLAUDE_TOOL_INPUT (JSON)
# to extract subagent_type and prompt for classification.

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

# Only check Agent tool
if [[ "$TOOL_NAME" != "Agent" ]]; then
    exit 0
fi

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Parse subagent_type and prompt from JSON using python3
PARSE_RESULT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    data = {}
agent_type = data.get('subagent_type', '') or ''
prompt = data.get('prompt', '') or ''
print(agent_type)
print(prompt)
" "$TOOL_INPUT" 2>/dev/null)

AGENT_TYPE=$(echo "$PARSE_RESULT" | head -n 1)
PROMPT=$(echo "$PARSE_RESULT" | tail -n +2)
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Determine if this is an Explore or general-purpose agent
IS_BLOCKED_TYPE=false
if [[ -z "$AGENT_TYPE" || "$AGENT_TYPE" == "Explore" || "$AGENT_TYPE" == "general-purpose" ]]; then
    IS_BLOCKED_TYPE=true
fi

# Check for audit/review keywords and suggest the correct agent
if [[ "$IS_BLOCKED_TYPE" == true ]]; then
    SUGGESTION=""

    if echo "$PROMPT_LOWER" | grep -qi "owasp\|security scan"; then
        SUGGESTION="security-engineer (via /security-review skill)"
    elif echo "$PROMPT_LOWER" | grep -qi "coverage analysis\|test gaps"; then
        SUGGESTION="qa-engineer (via /qa-test-strategy skill)"
    elif echo "$PROMPT_LOWER" | grep -qi "audit\|review\|compliance\|solid\|dry"; then
        SUGGESTION="code-reviewer (via /code-review skill)"
    fi

    if [[ -n "$SUGGESTION" ]]; then
        echo "BLOCKED: Explore/general-purpose agent spawned with audit/review keywords." >&2
        echo "  Agent type: '${AGENT_TYPE:-<empty/general-purpose>}'" >&2
        echo "  Use instead: $SUGGESTION" >&2
        echo "  Invoke the corresponding skill — it will spawn the correct specialist agent." >&2
        exit 2
    fi
fi

# Suppress advisory for Parallel Dispatch Protocol
if echo "$PROMPT_LOWER" | grep -qi "skill.md"; then
    exit 0
fi

# Advisory reminder for all non-blocked cases
echo "SKILL CHECK REMINDER: Before spawning an agent, verify:" >&2
echo "  - Is there a skill for this phase? (/build-implementation, /refactor, /bug-fix, /code-review, /security-review, /verify, /qa-test-strategy, /product-acceptance)" >&2
echo "  - If yes: invoke the skill first — the skill structures agent spawning." >&2
echo "  - If this agent is being spawned BY a skill: proceed." >&2

# Allow — advisory only
exit 0
