#!/usr/bin/env bash
# Runtime guard — PreToolUse Agent|Bash|Write|Edit hook.
# Mode A (Agent): record start file. Mode B (Bash|Write|Edit): scan for over-cap.
# Read intentionally excluded (highest-volume, fast-bounded).
# See rules/agent-protocol.md > Resource Bounds.

set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/resource-bounds.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-key.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-record.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-check.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

_rg_runtime_dir() {
  local sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  echo "$HOME/.claude/metrics/${sid:-local-$$}/subagent-runtimes"
}

_rg_record() {
  local stype name team key class display
  stype=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // ""')
  name=$(echo "$INPUT" | jq -r '.tool_input.name // ""')
  team=$(echo "$INPUT" | jq -r '.tool_input.team_name // ""')
  key=$(_rg_compute_key "$stype" "$name" "$team")
  class=$(_rg_class_of "$team"); display="${name:-$stype}"
  _rg_write_start "$(_rg_runtime_dir)" "$key" "$class" "$display"
}

_rg_dispatch() {
  case "$TOOL_NAME" in
    Agent) _rg_record; exit 0 ;;
    Bash|Write|Edit) _rg_scan_dir "$(_rg_runtime_dir)" || exit 2; exit 0 ;;
    *) exit 0 ;;
  esac
}

_rg_dispatch
