#!/usr/bin/env bash
# PreToolUse hook: scope-guards the planning-agent's Edit access.
# Allows only edits to <repo>/pipeline-state/<id>-plan.md files (where <id>
# is a single path-segment matching ^[A-Za-z0-9_-]+-plan\.md$).
# Other paths: exit 2 (blocked) and logged.
#
# Reads the standard PreToolUse stdin JSON (peer hook convention). The harness
# does NOT populate CLAUDE_TOOL_NAME / CLAUDE_SUBAGENT_TYPE /
# CLAUDE_TOOL_INPUT_FILE_PATH for this hook category — env-var sourcing is a
# silent no-op. See hooks/pre-agent-allowlist.sh and hooks/depth-guard.sh for
# the canonical stdin pattern.
#
# enforces: rules/_detail/parallel-dispatch-protocol.md:Planning Agent
# protects: build-implementation
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
SESSION_RAW=$(echo "$INPUT" | jq -r '.session_id // empty')
SESSION=$(printf '%s' "$SESSION_RAW" | tr -dc 'A-Za-z0-9_-' | head -c 64)
[[ -z "$SESSION" ]] && SESSION="unknown"

[[ "$SUBAGENT_TYPE" != "planning-agent" ]] && exit 0
case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

# Anchored allow-check: file must (a) live inside <repo>/pipeline-state and
# (b) have a basename matching ^[A-Za-z0-9_-]+-plan\.md$. Path is normalised
# via python's os.path.realpath so `..` traversal collapses BEFORE the
# prefix compare, even when the target file does not exist (macOS BSD
# realpath returns empty for non-existent files; relying on it would let
# `pipeline-state/../../etc/x-plan.md` slip through the prefix check).
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT=$(git -C "$HOOK_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$HOME/.claude")
ALLOWED_DIR=$(python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$WORKTREE_ROOT/pipeline-state" 2>/dev/null || echo "$WORKTREE_ROOT/pipeline-state")
REAL_FILE=$(python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")
BASENAME=$(basename -- "$REAL_FILE")
PARENT_DIR=$(dirname -- "$REAL_FILE")
PARENT_NAME=$(basename -- "$PARENT_DIR")

# DUAL_PATH: allow legacy <id>-plan.md OR new-layout plan.md under pipeline-state/<id>/.
if [[ "$REAL_FILE" == "$ALLOWED_DIR"/* ]]; then
  [[ "$BASENAME" =~ ^[A-Za-z0-9_-]+-plan\.md$ ]] && exit 0
  [[ "$BASENAME" == "plan.md" && "$PARENT_NAME" =~ ^[A-Za-z0-9_-]+$ && "$PARENT_DIR" != "$ALLOWED_DIR" ]] && exit 0
fi

LOG_DIR="${HOME:-/tmp}/.claude/metrics/$SESSION"
mkdir -p "$LOG_DIR" 2>/dev/null || exit 2
LOG_FILE="$LOG_DIR/planning-agent-scope-violations.jsonl"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -nc \
  --arg ts "$TS" \
  --arg subagent "planning-agent" \
  --arg tool "$TOOL_NAME" \
  --arg path "$FILE_PATH" \
  --arg session "$SESSION" \
  '{ts:$ts, record_type:"edit_scope_blocked", subagent_type:$subagent, tool:$tool, attempted_path:$path, session_id:$session, action:"blocked"}' \
  >> "$LOG_FILE" 2>/dev/null

echo "BLOCKED: planning-agent may only Edit pipeline-state/*-plan.md files. Attempted: $FILE_PATH" >&2
exit 2
