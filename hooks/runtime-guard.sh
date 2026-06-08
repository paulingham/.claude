#!/usr/bin/env bash
# Runtime guard — PreToolUse Agent|Bash|Write|Edit hook.
# Mode A (Agent): record start file. Mode B (Bash|Write|Edit): scan for over-cap.
# Read intentionally excluded (highest-volume, fast-bounded).
# See protocols/agent-protocol.md > Resource Bounds.
# Historical per-call durations are captured separately by hooks/tool-timing-capture.sh
# to metrics/{session}/tool-timings.jsonl. This guard owns wall-clock cap ENFORCEMENT only.
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline, all-skills

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/resource-bounds.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-key.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-respawn.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-record.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-emit.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-check.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-dispatch.sh"  # _rg_dispatch + helpers

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)

_rg_dispatch
