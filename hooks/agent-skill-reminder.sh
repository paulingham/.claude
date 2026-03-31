#!/bin/bash
# Agent Skill Reminder — PreToolUse hook for Agent tool
#
# Three checks in order:
#   1. HARD BLOCK (exit 2): Write-capable agents MUST use isolation: worktree.
#   2. HARD BLOCK (exit 2): Explore and general-purpose agents are universally
#      blocked. All tasks must use specialized agent types.
#   3. ADVISORY (exit 0): Reminds the orchestrator to check if a skill should
#      have been invoked before spawning any other agent.
#
# This hook fires BEFORE every Agent spawn. It reads CLAUDE_TOOL_INPUT (JSON)
# to extract subagent_type, prompt, and isolation for classification.

# Hook profile
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Only check Agent tool
if [[ "$TOOL_NAME" != "Agent" ]]; then
    exit 0
fi

TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')

# Parse subagent_type, prompt, and isolation from tool_input JSON using python3
PARSE_RESULT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    data = {}
agent_type = data.get('subagent_type', '') or ''
prompt = data.get('prompt', '') or ''
isolation = data.get('isolation', '') or ''
print(agent_type)
print(isolation)
print(prompt)
" "$TOOL_INPUT" 2>/dev/null)

AGENT_TYPE=$(echo "$PARSE_RESULT" | head -n 1)
ISOLATION=$(echo "$PARSE_RESULT" | sed -n '2p')
PROMPT=$(echo "$PARSE_RESULT" | tail -n +3)
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Worktree enforcement for write-capable agents
WRITE_CAPABLE_TYPES="software-engineer frontend-engineer qa-engineer database-engineer infrastructure-engineer"
IS_WRITE_CAPABLE=false
for wc_type in $WRITE_CAPABLE_TYPES; do
    if [[ "$AGENT_TYPE" == "$wc_type" ]]; then
        IS_WRITE_CAPABLE=true
        break
    fi
done

if [[ "$IS_WRITE_CAPABLE" == true ]]; then
    if [[ "$ISOLATION" != *"worktree"* ]]; then
        echo "BLOCKED: Write-capable agent '$AGENT_TYPE' MUST be spawned with isolation: worktree. See rules/agent-protocol.md." >&2
        exit 2
    fi
fi

# Universal block on Explore and general-purpose agents
if [[ -z "$AGENT_TYPE" || "$AGENT_TYPE" == "Explore" || "$AGENT_TYPE" == "general-purpose" ]]; then
    echo "BLOCKED: Explore and general-purpose agents are not permitted. Use a specialized agent type instead. See rules/agent-protocol.md for the pattern-to-agent mapping." >&2
    exit 2
fi

# HARD BLOCK: Reviewers MUST receive pre-computed diff
REVIEWER_TYPES="code-reviewer security-engineer"
IS_REVIEWER=false
for r_type in $REVIEWER_TYPES; do
    if [[ "$AGENT_TYPE" == "$r_type" ]]; then
        IS_REVIEWER=true
        break
    fi
done

if [[ "$IS_REVIEWER" == true ]]; then
    if ! echo "$PROMPT_LOWER" | grep -qi "full diff\|changed file\|git diff"; then
        echo "BLOCKED: Reviewer agent '$AGENT_TYPE' MUST receive pre-computed diff and changed file contents in the prompt. See rules/parallel-dispatch-protocol.md:19." >&2
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
