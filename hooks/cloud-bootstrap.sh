#!/usr/bin/env bash
# cloud-bootstrap.sh — SessionStart hook for Claude Code on the web.
#
# When the cloud platform clones the harness into $CLAUDE_PROJECT_DIR (e.g.
# /home/user/.claude) but Claude Code's loader looks at $HOME/.claude (e.g.
# /root/.claude), this hook symlinks the harness artifacts into $HOME/.claude
# so skills, agents, hooks, and settings.json are visible at session start.
#
# Wire this hook into $HOME/.claude/settings.json with a SessionStart entry:
#   "SessionStart": [{
#     "matcher": "",
#     "hooks": [{ "type": "command", "command": "$CLAUDE_PROJECT_DIR/hooks/cloud-bootstrap.sh" }]
#   }]
#
# The hook runs in async mode so session start is not blocked. On desktop
# (where $HOME/.claude IS the harness) the hook is a no-op.

set -uo pipefail

echo '{"async": true, "asyncTimeout": 60000}'
exec >&2

if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  echo "cloud-bootstrap: CLAUDE_PROJECT_DIR unset; nothing to link" >&2
  exit 0
fi

LIB="$CLAUDE_PROJECT_DIR/scripts/_lib/cloud-link.sh"
if [ ! -f "$LIB" ]; then
  echo "cloud-bootstrap: $LIB missing; cannot bootstrap" >&2
  exit 0
fi

# shellcheck source=../scripts/_lib/cloud-link.sh
. "$LIB"

if ! cloud_link_should_run; then
  exit 0
fi

cloud_link_harness "$CLAUDE_PROJECT_DIR" "$HOME/.claude" >&2
