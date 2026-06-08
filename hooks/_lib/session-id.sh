#!/usr/bin/env bash
# Single source of truth for the per-session id used to scope the intake-backstop
# marker (intake-markers/$SID.marker). Source this file; call resolve_session_id.
#
# WHY A SHARED HELPER: the intake marker round-trip only works if the writer
# (intake-fingerprint-audit.sh), the reader (intake-backstop.sh) and the clearer
# (session-start-bootstrap.sh) derive the IDENTICAL SID for the same session. A
# copy-pasted snippet drifted into env-based derivation (`${CLAUDE_SESSION_ID:-local-$$}`),
# but CLAUDE_SESSION_ID is NOT set in this harness's hook env, so `local-$$` fell
# back to the hook subprocess PID — a DIFFERENT value on every hook invocation.
# The writer wrote local-<PID_A>.marker; the reader looked for local-<PID_B>.marker;
# they never matched; the gate over-blocked every command after a real /intake.
#
# THE RELIABLE CHANNEL: the harness injects a stable per-session id into every
# hook's STDIN JSON as `.session_id` (the same field bug-fixed-payload-validator.sh
# and planning-agent-edit-scope.sh already read). Precedence below:
#   1. stdin `.session_id`  — the reliable channel
#   2. $CLAUDE_SESSION_ID env — in case a future context sets it
#   3. local-$$            — last-resort fallback (degrades to over-block, never under-block)
# The result is sanitised to [A-Za-z0-9_-] so it is always a safe filename.

# resolve_session_id <input_json>
#   <input_json>: the raw hook stdin JSON (may be empty). Echoes the sanitised SID.
resolve_session_id() {
  local input_json="${1:-}"
  local sid_raw=""

  if [[ -n "$input_json" ]]; then
    sid_raw=$(printf '%s' "$input_json" | jq -r '.session_id // empty' 2>/dev/null)
  fi
  [[ -z "$sid_raw" ]] && sid_raw="${CLAUDE_SESSION_ID:-}"
  [[ -z "$sid_raw" ]] && sid_raw="local-$$"

  local sid="${sid_raw//[^A-Za-z0-9_-]/}"
  [[ -z "$sid" ]] && sid="local-$$"
  printf '%s' "$sid"
}
