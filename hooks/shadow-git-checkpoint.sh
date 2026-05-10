#!/usr/bin/env bash
# Shadow git checkpoint — PostToolUse on Write|Edit|NotebookEdit.
# Captures the active worktree's pending changes to refs/checkpoints/<task>/<slug>-<N>
# after every file-mutating tool call inside an active pipeline's worktree.
# Provides per-tool-use rollback granularity for Build/PDR-RTV agents.
#
# Iron Law 4: every git op uses `git -C "$WT"` delegation. Hook never blocks
# the originating tool call (always exits 0). Forensic JSONL emission via
# python3 json.dumps (F5 instinct — never printf-with-%s).
#
# enforces: rules/_detail/agent-protocol.md:Main-Branch Invariant
# protects: build-implementation, pdr-rtv

set -euo pipefail

# Sentinel string for the "clean worktree, nothing to checkpoint" path. Used
# by both the error-state assignment and the downstream success-coercion so
# the two sites can never drift on the literal value.
readonly _SGC_NO_CHANGES="no-changes-to-capture"

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse"
trap 'log_hook_event $?' EXIT

# AC2.2 — escape-hatch BEFORE any work, but AFTER trap registration (F3 instinct).
[[ "${CLAUDE_DISABLE_SHADOW_CHECKPOINT:-}" == "1" ]] && exit 0
[[ "${CLAUDE_HOOK_PROFILE:-}" == "minimal" ]] && exit 0

# AC2.3 — tool input via stdin+jq (F7 instinct: env vars are not populated for hook events).
INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Source helpers (Slice 1).
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/shadow-checkpoint-helpers.sh"

# AC2.4 — worktree resolution (no-op if file_path is outside any agent worktree).
WT=$(_sgc_resolve_worktree "$FILE_PATH" 2>/dev/null) || exit 0
[[ -z "$WT" ]] && exit 0

# Worktree slug = basename(WT). Validate before using it as a ref-name component.
SLUG=$(basename "$WT")
_sgc_validate_id "$SLUG" || exit 0

# AC2.5 — task-id resolution (no-op if no active pipeline).
TASK=$(_sgc_resolve_task_id 2>/dev/null) || exit 0
[[ -z "$TASK" ]] && exit 0
_sgc_validate_id "$TASK" || exit 0

# Increment counter (under mutex). State directory mirrors pipeline-state layout.
STATE_DIR="${CLAUDE_PIPELINE_STATE_DIR:-$HOME/.claude/pipeline-state}"
TASK_DIR="$STATE_DIR/$TASK"
STEP=$(_sgc_increment_counter "$TASK_DIR" "$SLUG" 2>/dev/null) || STEP=""

# Build canonical ref name. Validation re-runs inside _sgc_ref_name.
REF=$(_sgc_ref_name "$TASK" "$SLUG" "$STEP" 2>/dev/null) || REF=""

# Forensic-log directory (mirrors tool-timing-capture pattern).
SID_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SID="${SID_RAW//[^A-Za-z0-9_-]/}"
[[ -z "$SID" ]] && SID="local-$$"
LOG_DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}/$SID"
mkdir -p "$LOG_DIR" 2>/dev/null || true
LOG_FILE="$LOG_DIR/shadow-checkpoints.jsonl"

# Capture start clock for duration_ms.
START_NS=$(python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)

# AC2.6 — happy path: stash create + update-ref under git -C "$WT" delegation.
# Retry on git/index.lock contention (concurrent PostToolUse fires on same WT).
SHA=""
ERROR=""
_sgc_stash_create() {
  local i=0
  while [[ $i -lt 10 ]]; do
    SHA=$(git -C "$WT" stash create 2>/dev/null) && return 0
    i=$((i + 1))
    sleep 0.05
  done
  return 1
}
if [[ -n "$STEP" && -n "$REF" ]]; then
  if _sgc_stash_create; then
    if [[ -n "$SHA" ]]; then
      git -C "$WT" update-ref "$REF" "$SHA" 2>/dev/null || ERROR="git-update-ref-failed"
    else
      # AC2.7 — clean worktree (no diff vs HEAD). Graceful skip.
      ERROR="$_SGC_NO_CHANGES"
      printf 'shadow-checkpoint: no changes to capture\n' >&2
    fi
  else
    ERROR="git-stash-create-failed"
    printf 'shadow-checkpoint: git stash create failed\n' >&2
  fi
else
  ERROR="counter-or-ref-name-failed"
fi

END_NS=$(python3 -c 'import time; print(int(time.time()*1000))' 2>/dev/null || echo 0)
DURATION=$((END_NS - START_NS))
[[ $DURATION -lt 0 ]] && DURATION=0

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SUCCESS="true"
[[ -n "$ERROR" ]] && SUCCESS="false"
# Treat the no-changes path as a successful no-op for forensics filtering: the
# hook did its job, the worktree just had nothing to capture. Other paths with
# ERROR set are real failures.
[[ "$ERROR" == "$_SGC_NO_CHANGES" ]] && SUCCESS="true"

# AC2.11, AC2.13 — forensic JSONL via python3 json.dumps (NEVER printf with %s).
python3 - "$TS" "$TASK" "$SLUG" "$STEP" "$REF" "$SHA" "$DURATION" "$SUCCESS" "$ERROR" "$LOG_FILE" <<'PY' 2>/dev/null || true
import json, sys
ts, task, slug, step, ref, sha, dur, success, err, log_file = sys.argv[1:11]
record = {
    "ts": ts,
    "hook": "shadow-git-checkpoint",
    "task_id": task,
    "worktree_slug": slug,
    "step": step,
    "ref": ref,
    "sha": sha,
    "duration_ms": int(dur) if dur.lstrip("-").isdigit() else 0,
    "success": success == "true",
}
if err:
    record["error"] = err
with open(log_file, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, separators=(",", ":")) + "\n")
PY

exit 0
