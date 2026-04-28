#!/usr/bin/env bash
# WorktreeCreate hook — called by Claude Code instead of built-in git worktree creation.
# Receives JSON via stdin: { "tool_input": { "path": "...", "branch": "..." } }
set -euo pipefail

INPUT=$(cat)
WORKTREE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // empty')
BRANCH=$(echo "$INPUT" | jq -r '.tool_input.branch // empty')

if [[ -z "$WORKTREE_PATH" ]]; then
  echo '{"error":"missing path"}' >&2
  exit 1
fi

# Determine the repo root (the project dir, not ~/.claude)
REPO_ROOT=$(echo "$INPUT" | jq -r '.tool_input.repo_root // empty')
if [[ -z "$REPO_ROOT" ]]; then
  # Fall back: walk up from the path to find the git root
  REPO_ROOT=$(git -C "$(dirname "$WORKTREE_PATH")" rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [[ -z "$REPO_ROOT" ]]; then
  echo '{"error":"cannot determine repo root"}' >&2
  exit 1
fi

if [[ -n "$BRANCH" ]]; then
  git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH" 2>&1
else
  git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" 2>&1
fi
