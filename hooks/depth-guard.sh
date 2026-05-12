#!/usr/bin/env bash
# Depth guard — PreToolUse Agent hook.
# Refuses subagent spawn when CLAUDE_SUBAGENT_DEPTH >= max (default 3).
# See rules/agent-protocol.md > Resource Bounds.
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline, build-implementation

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/resource-bounds.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/depth-guard-log.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "Agent" ]] && exit 0

_dg_resolve_depth() {
  local raw="${CLAUDE_SUBAGENT_DEPTH:-0}"
  case "$raw" in ''|*[!0-9]*) echo 0 ;; *) echo "$raw" ;; esac
}

_dg_block() {
  local depth="$1" max="$2" stype="$3"
  printf 'BLOCKED: subagent max recursion depth exceeded.\n' >&2
  printf '  current depth: %s, max: %s\n' "$depth" "$max" >&2
  printf 'See rules/agent-protocol.md > Resource Bounds.\n' >&2
  _dg_log_violation "$depth" "$max" "$stype"
}

DEPTH=$(_dg_resolve_depth)
MAX=$(_max_depth)
STYPE="${SUBAGENT_TYPE:-unknown}"

[[ "$DEPTH" -lt "$MAX" ]] && exit 0
_dg_block "$DEPTH" "$MAX" "$STYPE"
exit 2
