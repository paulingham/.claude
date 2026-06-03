#!/usr/bin/env bash
# WorktreeCreate hook — called by Claude Code instead of built-in git worktree creation.
# Receives JSON via stdin: { "tool_input": { "path": "...", "branch": "..." } }
#
# enforces: protocols/agent-protocol.md:Main-Branch Invariant
# protects: build-implementation
set -euo pipefail

INPUT=$(cat)
WORKTREE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // empty')
BRANCH=$(echo "$INPUT" | jq -r '.tool_input.branch // empty')

# Determine the repo root (the project dir, not ~/.claude)
REPO_ROOT=$(echo "$INPUT" | jq -r '.tool_input.repo_root // empty')
if [[ -z "$REPO_ROOT" ]]; then
  if [[ -n "$WORKTREE_PATH" ]]; then
    REPO_ROOT=$(git -C "$(dirname "$WORKTREE_PATH")" rev-parse --show-toplevel 2>/dev/null || echo "")
  fi
  if [[ -z "$REPO_ROOT" ]]; then
    REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
  fi
fi

if [[ -z "$REPO_ROOT" ]]; then
  echo '{"error":"cannot determine repo root"}' >&2
  exit 1
fi

# If the harness did not supply tool_input.path (current behaviour for
# Agent({isolation:"worktree"}) spawns), generate one under the repo's
# .claude/worktrees/agent-<rand>. The harness-of-harness convention is
# tracked at protocols/agent-protocol.md > Worktree Lifecycle.
if [[ -z "$WORKTREE_PATH" ]]; then
  RAND=$(openssl rand -hex 4 2>/dev/null || printf '%s' "$RANDOM$RANDOM" | head -c 8)
  WORKTREE_PATH="$REPO_ROOT/.claude/worktrees/agent-${RAND}"
  mkdir -p "$(dirname "$WORKTREE_PATH")"
fi

if [[ -n "$BRANCH" ]]; then
  git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "$BRANCH" >&2
else
  git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" >&2
fi
# Harness reads stdout to discover the new worktree path; git's own progress
# output goes to stderr so it doesn't pollute the path channel.
echo "$WORKTREE_PATH"
