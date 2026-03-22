#!/usr/bin/env bash
# Auto-PR Advisory Hook — Stop event
# Detects when a feature branch has commits ahead of main and suggests /pr-creation.
# Advisory only — never blocks.

set -uo pipefail
# Deliberately omitting -e: this is advisory-only, individual command failures should not abort

INPUT=$(cat)

# Never block if stop_hook_active (avoid loops)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Get current branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ -z "$BRANCH" ]; then
  exit 0
fi

# Sanitize branch name — strip anything that isn't alphanumeric, /, -, _, .
BRANCH="${BRANCH//[^a-zA-Z0-9\/_.-]/}"

# Skip if on main/master
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  exit 0
fi

# Check for commits ahead of main
BASE_BRANCH="main"
git rev-parse "$BASE_BRANCH" >/dev/null 2>&1 || BASE_BRANCH="master"
git rev-parse "$BASE_BRANCH" >/dev/null 2>&1 || exit 0

AHEAD=$(git log "${BASE_BRANCH}..HEAD" --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$AHEAD" -eq 0 ]; then
  exit 0
fi

# Check for uncommitted changes (if so, skip — not ready for PR)
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNCOMMITTED" -gt 0 ]; then
  exit 0
fi

# Advisory output — suggest /pr-creation
echo "AUTO-PR: Branch '${BRANCH}' has ${AHEAD} commit(s) ahead of ${BASE_BRANCH} and no uncommitted changes. Consider running /pr-creation to open a pull request."

exit 0
