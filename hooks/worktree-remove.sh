#!/usr/bin/env bash
# WorktreeRemove hook — called by Claude Code to remove a worktree.
# Receives JSON via stdin: { "tool_input": { "path": "..." } }
#
# enforces: protocols/agent-protocol.md:Main-Branch Invariant
# protects: build-implementation
set -euo pipefail

INPUT=$(cat)
WORKTREE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // empty')

if [[ -z "$WORKTREE_PATH" ]]; then
  echo '{"error":"missing path"}' >&2
  exit 1
fi

REPO_ROOT=$(git -C "$WORKTREE_PATH" rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
  # Already gone — succeed silently
  exit 0
fi

git -C "$REPO_ROOT" worktree remove "$WORKTREE_PATH" --force 2>&1 || true
