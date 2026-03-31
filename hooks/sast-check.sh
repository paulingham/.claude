#!/bin/bash
# SAST Check — PreToolUse hook for PR creation
# Runs static analysis security testing on changed files before PR creation.
# Hard blocks (exit 2) if HIGH/ERROR severity issues found.
# Falls back to bearer if semgrep unavailable. Advisory skip if neither present.

set -uo pipefail

# Hook profile (standard — runs alongside quality-gate)
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only check Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Only check PR creation commands
if [[ ! "$COMMAND" =~ "gh pr create" ]]; then
    exit 0
fi

echo "SAST: Running static analysis security scan..." >&2

CHANGED_FILES=$(git diff --name-only main...HEAD 2>/dev/null || true)

if [[ -z "$CHANGED_FILES" ]]; then
    echo "SAST: No changed files detected. Skipping." >&2
    exit 0
fi

if command -v semgrep &> /dev/null; then
    echo "SAST: Using semgrep on changed files..." >&2
    SEMGREP_OUTPUT=$(echo "$CHANGED_FILES" | xargs semgrep scan --config auto --error --severity ERROR --severity WARNING 2>&1)
    SEMGREP_EXIT=$?

    if [[ $SEMGREP_EXIT -ne 0 ]]; then
        echo "" >&2
        echo "SAST FAILED: semgrep found HIGH/ERROR severity issues:" >&2
        echo "$SEMGREP_OUTPUT" | tail -20 >&2
        echo "" >&2
        exit 2
    fi

    echo "SAST PASSED: No high-severity issues found." >&2
    exit 0
fi

if command -v bearer &> /dev/null; then
    echo "SAST: semgrep not found. Using bearer..." >&2
    BEARER_OUTPUT=$(bearer scan . 2>&1)
    BEARER_EXIT=$?

    if [[ $BEARER_EXIT -ne 0 ]]; then
        echo "" >&2
        echo "SAST WARNING: bearer found issues:" >&2
        echo "$BEARER_OUTPUT" | tail -20 >&2
        echo "" >&2
        exit 2
    fi

    echo "SAST PASSED: bearer scan clean." >&2
    exit 0
fi

echo "SAST: No static analysis tool found (install semgrep: pip install semgrep). Skipping." >&2
exit 0
