#!/usr/bin/env bash
# verification-freshness-guard — PreToolUse Agent hook.
# Compares verification-evidence.json git_head against worktree HEAD on gated roles.
# Path-B advisory: log-only at v2.1.141, blocks once permissionDecision ships on Agent matcher.
# Promotion criterion: protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md § Promotion Criterion.
#
# enforces: rules/core.md:Iron Law 2
# protects: verify, patch-critique, pr-creation, product-acceptance
# if-broken-look-at: protocols/pipeline-protocol.md § In-Cycle Fix Rule (the staleness root cause)

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

[[ "${CLAUDE_DISABLE_FRESHNESS_GUARD:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-freshness.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0
printf '%s' "$INPUT" | bash "${HOOK_DIR}/_lib/log-injection.sh" "$RESOLVED" "path-b-advisory" "freshness-guard.jsonl" 2>/dev/null

# TODO(v2.1.142): replace exit 0 below with exit 2 in the would_block branch after
# permissionDecision ships and Promotion Criterion (see proposal) is met.
exit 0
