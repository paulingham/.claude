#!/usr/bin/env bash
# stuck-guard — Stop hook entrypoint for the semantic stuck-detector.
# Shipped ADVISORY (log-only): always exits 0, never blocks.
# Disable escape: CLAUDE_DISABLE_STUCK_GUARD=1 → skip entirely.
#
# enforces: protocols/operational-protocol.md (advisory) semantic loop detection per OpenHands five-pattern algorithm
# protects: pipeline (advisory only at current version)
# if-broken-look-at: hooks/_lib/stuck-detector.py, hooks/_lib/stuck_patterns.py

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT

[[ "${CLAUDE_DISABLE_STUCK_GUARD:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)

# Avoid Stop recursion — if stop_hook_active is true, exit as a pure no-op.
# A nested Stop firing must not write forensic JSONL (it would double-count),
# so we neutralise the EXIT-trap logger before exiting. See
# knowledge/stop-hook-active-checklist.md.
STOP_ACTIVE=$(printf '%s' "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stop_hook_active','false'))" 2>/dev/null || echo "false")
if [[ "$STOP_ACTIVE" == "True" || "$STOP_ACTIVE" == "true" ]]; then
  trap - EXIT
  exit 0
fi

# shellcheck source=/dev/null
source "${HOOK_DIR}/loop-guard.sh" && check_stuck "$INPUT"

exit 0
