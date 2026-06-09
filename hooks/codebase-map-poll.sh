#!/usr/bin/env bash
# Codebase-map Stop poll hook. Reads cached `last_built_sha` and runs
# `git rev-parse HEAD`; rebuilds only when the SHA advances. Reuses the
# shared flock to serialize against the SessionStart hook. Always exits
# 0 (subprocess-isolates the generator per AC18, degrades on AC21
# catch surface).
#
# enforces: protocols/autonomous-intelligence.md:Codebase Map
# protects: codebase-map-poll

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT    # MUST register BEFORE the disable check

# Nested Stop firing (stop_hook_active) must be a pure no-op — neutralise the
# EXIT-trap logger so no forensic JSONL / map rebuild fires recursively.
INPUT=$(cat 2>/dev/null) || INPUT=""
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && { trap - EXIT; exit 0; }

check_bypass_gate "CLAUDE_DISABLE_CODEBASE_MAP" && exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

LIB_DIR="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib"
# shellcheck disable=SC1091
source "$LIB_DIR/project-hash.sh"
# shellcheck disable=SC1091
source "$LIB_DIR/codebase-map-flock.sh"
# shellcheck disable=SC1091
source "$LIB_DIR/codebase-map-common.sh"

HASH=$(_cbm_resolve_hash "$LIB_DIR")
SESSION=$(_cbm_session_id)
CACHE_DIR="$HARNESS_DATA/db/codebase-map/$HASH"
STATE_FILE="$CACHE_DIR/state.json"
METRICS_FILE="${CLAUDE_HOOK_LOG_DIR:-$HARNESS_DATA/metrics}/$SESSION/codebase-map-rebuild.jsonl"
mkdir -p "$CACHE_DIR" "$(dirname "$METRICS_FILE")"

REPO_ROOT="${CLAUDE_CODEBASE_MAP_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SHA_BEFORE="$(/usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" read "$STATE_FILE" --field last_built_sha 2>/dev/null || echo "")"
SHA_AFTER="$(/usr/bin/git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "")"

# AC17: no-op when SHA unchanged — DOES NOT acquire the flock and DOES
# NOT emit a JSONL line (the rebuild never happened).
if [[ -n "$SHA_BEFORE" && "$SHA_BEFORE" == "$SHA_AFTER" ]]; then
  exit 0
fi

# Persist new SHA BEFORE rebuild (state-before-expensive-op).
[[ -n "$SHA_AFTER" ]] && /usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" write "$STATE_FILE" "$SHA_AFTER" 2>/dev/null || true

_cbm_poll_rebuild() {
  # AC18 contract: invocation is `python3 -m codebase_map.cli build <root> <cache>`
  # via the shared _cbm_invoke_and_emit helper. Argv form only; inline
  # import-from-bash is forbidden.
  _cbm_invoke_and_emit \
    "$LIB_DIR" "poll" \
    "$REPO_ROOT" "$CACHE_DIR" "$METRICS_FILE" \
    "$SHA_BEFORE" "$SHA_AFTER"
}

with_codebase_map_lock "$HASH" -- _cbm_poll_rebuild
exit 0
