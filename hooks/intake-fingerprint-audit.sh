#!/usr/bin/env bash
# Intake fingerprint audit — PostToolUse hook for Skill matcher (advisory/log-only).
# Writes one JSONL line per /intake invocation to metrics/{session}/intake-overrides.jsonl.
# Single-source task_id resolution: tool_response parse of [Intake] task_id: marker.
# NO mtime fallback (per plan HIGH-3). NEVER blocks (exit 0 on every path).
#
# enforces: protocols/work-class-routing.md:Hook implementation
# protects: pipeline, forensics

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/session-id.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" 2>/dev/null && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
[[ "$TOOL" != "Skill" ]] && exit 0

RESPONSE=$(printf '%s' "$INPUT" | jq -r '.tool_response // ""' 2>/dev/null)
TASK_ID=$(printf '%s' "$RESPONSE" | grep -oE '\[Intake\] task_id: [^[:space:]\\]+' | tail -1 | sed 's/^\[Intake\] task_id: //')
if [[ ! "$TASK_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then TASK_ID="<unknown>"; fi

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# SID from stdin .session_id (the reliable harness channel), then env, then
# local-$$. Identical derivation to intake-backstop.sh's reader and
# session-start-bootstrap.sh's clearer — they share _lib/session-id.sh so the
# marker round-trip cannot drift.
SID=$(resolve_session_id "$INPUT")
METRICS_DIR="${CLAUDE_HOOK_LOG_DIR:-$HARNESS_DATA/metrics}/$SID"
INTAKE_MD="$HARNESS_DATA/pipeline-state/$TASK_ID/intake.md"

python3 "${HOOK_DIR}/_lib/intake-fingerprint-emit.py" \
  "$METRICS_DIR" "$TS" "$TASK_ID" "$INTAKE_MD" 2>/dev/null || true

# Arm the intake-backstop gate: drop a per-session marker so subsequent
# orchestrator work-bash / specialized-spawn calls in THIS session pass the
# backstop. session-start-bootstrap.sh clears it per session (re-arming the
# gate). The reader (intake-backstop.sh) and clearer both derive SID via the
# same resolve_session_id helper, so the marker name is guaranteed to match.
mkdir -p "$HARNESS_DATA/intake-markers" 2>/dev/null || true
touch "$HARNESS_DATA/intake-markers/$SID.marker" 2>/dev/null || true

exit 0
