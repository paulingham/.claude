#!/usr/bin/env bash
# Codebase-map SessionStart rebuild hook. Walks the repo, rebuilds the
# generated codebase-map digest, persists `last_built_sha` to state.json
# BEFORE the expensive rebuild (memory `instinct-state-before-expensive-op`).
# Subprocess-isolates the generator (AC18) so SIGSEGV in tree-sitter
# native libs never poisons the hook's own exit code. Always exits 0.
#
# enforces: protocols/autonomous-intelligence.md:Codebase Map
# protects: codebase-map-rebuild

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT    # MUST register BEFORE the disable check

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

# AC16: persist new SHA BEFORE rebuild (state-before-expensive-op).
[[ -n "$SHA_AFTER" ]] && /usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" write "$STATE_FILE" "$SHA_AFTER" 2>/dev/null || true

_cbm_run_rebuild() {
  # AC18 contract: invocation is `python3 -m codebase_map.cli build <root> <cache>`
  # via the shared _cbm_invoke_and_emit helper. Argv form only; inline
  # import-from-bash is forbidden.
  _cbm_invoke_and_emit \
    "$LIB_DIR" "rebuild" \
    "$REPO_ROOT" "$CACHE_DIR" "$METRICS_FILE" \
    "$SHA_BEFORE" "$SHA_AFTER"
}

with_codebase_map_lock "$HASH" -- _cbm_run_rebuild
exit 0
