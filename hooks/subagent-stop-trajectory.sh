#!/usr/bin/env bash
# Trajectory recorder — SubagentStop hook
# Appends a structured record to the active pipeline trajectory file when an agent stops.
# Auto-detects the active pipeline from pipeline-state files, or uses CLAUDE_PIPELINE_TASK_ID if set.
#
# enforces: protocols/pipeline-protocol.md:Structured Pipeline State
# protects: pipeline, forensics

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

set -uo pipefail

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0
AGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // .agent_type // "unknown"' 2>/dev/null || echo "unknown")
SUBAGENT_ID=$(echo "$INPUT" | jq -r '.subagent_id // empty' 2>/dev/null || echo "")
[[ -z "$SUBAGENT_ID" ]] && SUBAGENT_ID="${CLAUDE_SESSION_ID:-sess}-${RANDOM}-$$"

# Auto-detect active pipeline from pipeline-state files
TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-}"

if [[ -z "$TASK_ID" ]]; then
  # Scan for active pipeline state files
  PIPELINE_DIR="${HOME}/.claude/pipeline-state"
  if [[ -d "$PIPELINE_DIR" ]]; then
    # Find pipeline files with in_progress verdict (check top-level and workstream subdirs)
    ACTIVE_FILE=$(grep -rl "verdict: in_progress" "$PIPELINE_DIR" 2>/dev/null | head -1)
    if [[ -n "$ACTIVE_FILE" ]]; then
      TASK_ID=$(grep "^task_id:" "$ACTIVE_FILE" 2>/dev/null | head -1 | sed 's/task_id: *//')
    fi
  fi
fi

if [[ -z "$TASK_ID" ]]; then
  exit 0  # No active pipeline — skip
fi

# Sanitize TASK_ID to prevent path traversal — drop '.' (R10 hardening for new layout).
TASK_ID="${TASK_ID//[^a-zA-Z0-9_-]/}"

# Empty TASK_ID after sanitization (e.g. ".." input) → no write.
[[ -z "$TASK_ID" ]] && exit 0

# DUAL_PATH: write to new layout {task-id}/trajectory.jsonl.
TASK_DIR="${HOME}/.claude/pipeline-state/${TASK_ID}"
TRAJECTORY_FILE="${TASK_DIR}/trajectory.jsonl"

# Guard against path traversal — file must be under pipeline-state/
case "$TRAJECTORY_FILE" in
  "${HOME}/.claude/pipeline-state/"*) ;;
  *) exit 0 ;;
esac

if [[ ! -d "${HOME}/.claude/pipeline-state" ]]; then
  exit 0
fi
mkdir -p "$TASK_DIR" 2>/dev/null || exit 0

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -nc \
  --arg ts "$TIMESTAMP" \
  --arg agent "$AGENT_TYPE" \
  --arg task_id "$TASK_ID" \
  --arg subagent_id "$SUBAGENT_ID" \
  '{"timestamp":$ts,"agent":$agent,"event":"agent_stopped","task_id":$task_id,"subagent_id":$subagent_id}' \
  >> "$TRAJECTORY_FILE" 2>/dev/null || true

# Slice 3 / AC3.12 — runtime-guard start-file cleanup.
# Key derives from subagent_type ONLY (per-class) so cleanup matches spawn.
# shellcheck source=/dev/null
source "$(dirname "$0")/_lib/runtime-guard-key.sh" 2>/dev/null && {
  RG_KEY=$(_rg_compute_key "$AGENT_TYPE")
  SID="${CLAUDE_SESSION_ID:-local-$$}"; SID="${SID//[^a-zA-Z0-9_.-]/}"
  rm -f "$HOME/.claude/metrics/${SID:-local-$$}/subagent-runtimes/${RG_KEY}.start" 2>/dev/null || true
}

exit 0
