#!/bin/bash
# Quality Gate Hook - Final check before PR creation
# PreToolUse hook for Bash commands containing "gh pr create"
#
# This is the HARD BLOCK before PR creation:
# - All tests must pass
# - No uncommitted changes (optional warning)
# - Rubocop must be clean (errors level)

set -e

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
COMMAND="${CLAUDE_COMMAND:-}"

# Only check Bash commands
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Only check PR creation commands
if [[ ! "$COMMAND" =~ "gh pr create" ]]; then
    exit 0
fi

echo "QUALITY GATE: Running pre-PR checks..." >&2

FAILED=0

# Check 1: All tests must pass
echo "  Checking tests..." >&2
if command -v bundle &> /dev/null && [[ -f "Gemfile" ]]; then
    TEST_OUTPUT=$(bundle exec rspec --format progress 2>&1) || {
        echo "  FAILED: Tests are not passing" >&2
        echo "$TEST_OUTPUT" | tail -10 >&2
        FAILED=1
    }
    if [[ $FAILED -eq 0 ]]; then
        echo "  PASSED: All tests green" >&2
    fi
elif command -v npm &> /dev/null && [[ -f "package.json" ]]; then
    if ! npm test 2>&1 | tail -5; then
        echo "  FAILED: Tests are not passing" >&2
        FAILED=1
    else
        echo "  PASSED: All tests green" >&2
    fi
else
    echo "  SKIPPED: No test runner detected" >&2
fi

# Check 2: No uncommitted changes (warning only)
echo "  Checking git status..." >&2
if [[ -n "$(git status --porcelain)" ]]; then
    echo "  WARNING: Uncommitted changes detected" >&2
    git status --short >&2
    echo "  Please commit all changes before creating PR" >&2
fi

# Check 3: Rubocop (if available and Ruby project)
if command -v bundle &> /dev/null && [[ -f "Gemfile" ]]; then
    echo "  Running Rubocop..." >&2
    RUBOCOP_OUTPUT=$(bundle exec rubocop --format simple --fail-level E 2>&1) || {
        EXIT_CODE=$?
        if [[ $EXIT_CODE -ne 0 ]]; then
            echo "  FAILED: Rubocop errors detected" >&2
            echo "$RUBOCOP_OUTPUT" | tail -15 >&2
            FAILED=1
        fi
    }
    if [[ $FAILED -eq 0 ]] || [[ -z "${RUBOCOP_OUTPUT}" ]]; then
        echo "  PASSED: Rubocop clean" >&2
    fi
fi

# Check 4: Coverage check (if simplecov available)
if [[ -f "coverage/.last_run.json" ]]; then
    echo "  Checking coverage..." >&2
    COVERAGE=$(cat coverage/.last_run.json | jq -r '.result.line // 0' 2>/dev/null || echo "0")
    THRESHOLD=80
    if (( $(echo "$COVERAGE < $THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
        echo "  FAILED: Coverage ${COVERAGE}% is below ${THRESHOLD}% threshold" >&2
        FAILED=1
    else
        echo "  PASSED: Coverage ${COVERAGE}% meets threshold" >&2
    fi
fi

if [[ $FAILED -eq 1 ]]; then
    echo "" >&2
    echo "QUALITY GATE FAILED: Fix issues before creating PR" >&2
    echo "" >&2
    echo "Required before PR:" >&2
    echo "  1. All tests must pass" >&2
    echo "  2. No Rubocop errors" >&2
    echo "  3. All changes committed" >&2
    exit 2  # Block PR creation
fi

echo "QUALITY GATE PASSED: Proceeding with PR creation" >&2
exit 0
