#!/usr/bin/env bash
# pipeline-entry-guard — PreToolUse:Agent hook.
# Warns when a write-capable Build/Test agent is spawned without a verified
# pipeline-entry signal (task_id, active pipeline, or gear).
# Ships Path-B advisory: log + warn, spawn NOT blocked (exit 0).
# Promotion criterion: flip to enforcing (exit code change) once N=10 sessions confirm zero
# false-positive blocks (see promotion comment block below).
# NOTE: CLAUDE_METRICS_DIR is the top-priority override for ledger writes;
#       the 4-step metrics chain is: CLAUDE_METRICS_DIR > HARNESS_DATA >
#       CLAUDE_CONFIG_DIR > ~/.claude (mirroring agentic_security_gate_cli.py).
#
# enforces: CLAUDE.md § Process Lock (classify via /harness:intake first, no freelancing)
# protects: pipeline Build/Test phase governance
# if-broken-look-at: hooks/_lib/pipeline_entry_guard_cli.py (decision engine + signal gathering)
#                    $HARNESS_DATA/metrics/{session}/pipeline-entry-advisory.jsonl (advisory log)
#                    $HARNESS_DATA/metrics/{session}/pipeline-entry-bypass.jsonl (bypass log)

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
SUBAGENT_TYPE_SAFE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE_SAFE"' EXIT

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "Agent" ]] || exit 0

SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
# Sanitize to safe set before use in log/echo — prevents log injection via newlines or ANSI.
SUBAGENT_TYPE_SAFE="${SUBAGENT_TYPE//[^A-Za-z0-9_-]/_}"

DECISION=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/pipeline_entry_guard_cli.py")
if [[ $? -ne 0 ]]; then
    echo "pipeline-entry-guard: decision engine failed; failing open." >&2
    exit 0
fi
ACTION=$(printf '%s\n' "$DECISION" | sed -n '1p')
# REASON is intentionally not extracted — the warning message is fixed-form to prevent log injection.

case "$ACTION" in
    block)
        # Warning message is fixed-form (no raw REASON interpolation) to prevent log injection.
        echo "[pipeline-entry-guard] WARNING: ${SUBAGENT_TYPE_SAFE} spawned without a pipeline-entry signal — run /harness:intake or /harness:pipeline first. (advisory mode — spawn NOT blocked)" >&2
        # ADVISORY MODE (Path-B): log + warn only — spawn is NOT blocked.
        # PROMOTION CRITERION: flip the exit code on the line marked below once:
        #   N=10 distinct sessions have generated advisory events with ZERO confirmed
        #   false-positive blocks. Check session count:
        #     jq -r '.session_id' "$HARNESS_DATA"/metrics/*/pipeline-entry-advisory.jsonl \
        #       2>/dev/null | sort -u | wc -l
        # TODO(pipeline-entry-guard-promote): one-line flip — promote exit 0 to enforcing
        exit 0   # <-- SINGLE PROMOTION LINE
        ;;
    bypass)
        echo "pipeline-entry-guard bypassed via CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD=1" >&2
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
