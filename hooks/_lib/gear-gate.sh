#!/usr/bin/env bash
# Gear-gate helper — sourced by hooks that are Pipeline/Build-only bookkeeping
# with zero meaning in the PAIR gear (Phase B, GEAR-GATE bucket).
# Usage: check_gear_gate "$sid" || exit 0
#
# WHY KEYED ON SESSION ID, NOT PPID: hooks/_lib/gear-select.sh (a
# UserPromptSubmit hook) and each gear-gated hook (PreToolUse / SubagentStop /
# a CLI step invoked from a skill) are DIFFERENT subprocesses spawned by the
# harness per-event — they never share a PPID, so a PPID-keyed write can
# never round-trip to a PPID-keyed read (see hooks/_lib/session-id.sh for the
# identical prior incident with the intake-backstop marker). Session id is
# the one value that is genuinely stable for the whole session.
#
# The caller is responsible for resolving its own sid (typically via
# hooks/_lib/session-id.sh's resolve_session_id, from stdin JSON or
# $CLAUDE_SESSION_ID) and passing it in — this function does not read stdin
# itself, so it never competes with the host hook for the single stdin
# stream a PreToolUse hook needs to consume for its own payload.
#
# Contract:
#   Reads gear state written by hooks/_lib/gear-select.sh (key "gear-${sid}").
#   Returns 0 (RUN the hook) when gear is BUILD or PIPELINE, when the sid arg
#   is empty (unevaluable input), or when the gear state is UNREADABLE/absent
#   — fail toward doing the check, not skipping it (this is bookkeeping, not
#   a safety gate, but Iron Law 8's fail-closed posture still applies: an
#   unevaluable input must not silently no-op).
#   Returns 1 (SKIP/no-op) only on the affirmative, successfully-read PAIR case.
#
# enforces: protocols/pipeline-overview.md (Phase B hook re-homing)
# protects: pipeline-bookkeeping-hooks

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/state-dir.sh"

check_gear_gate() {
  local sid="${1:-}"
  [[ -z "$sid" ]] && return 0
  local gear
  gear=$(_state_read "gear-${sid}" 2>/dev/null) || return 0
  gear="${gear//$'\n'/}"
  [[ "$gear" == "PAIR" ]] && return 1
  return 0
}
