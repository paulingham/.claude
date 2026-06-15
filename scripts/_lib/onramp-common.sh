#!/usr/bin/env bash
# _lib/onramp-common.sh — shared helpers for new-skill / new-agent / new-hook.
# WHY: DRY the name-validation guard, event-validation guard, and confirm-prompt
#      so all three scaffolding scripts reject malformed input at parse time.
# Source this file; do NOT execute it directly.

# Valid name pattern: lowercase alphanumeric + hyphens, no leading/trailing hyphens.
_OC_NAME_RE='^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'

# Return 0 if <name> is safe; exit with error message otherwise.
_oc_validate_name() {
  local name="$1"
  if [[ ! "$name" =~ $_OC_NAME_RE ]]; then
    echo "ERROR: invalid name '$name'" >&2
    echo "  Names must match: ^[a-z0-9]([a-z0-9-]*[a-z0-9])?\$" >&2
    echo "  Use lowercase letters, digits, and hyphens only." >&2
    exit 1
  fi
}

# Canonical set of hook events — union of hooks.json + settings.json top-level keys.
# WHY: hard-coded to the ACTUAL keys so bogus events are caught before any file write.
_OC_VALID_EVENTS=(
  Notification
  PermissionRequest
  PostCompact
  PostToolUse
  PostToolUseFailure
  PreCompact
  PreToolUse
  SessionEnd
  SessionStart
  Stop
  StopFailure
  SubagentStart
  SubagentStop
  UserPromptSubmit
  WorktreeCreate
  WorktreeRemove
)

# Return 0 if <event> is in _OC_VALID_EVENTS; exit with error message otherwise.
_oc_validate_event() {
  local event="$1"
  local e
  for e in "${_OC_VALID_EVENTS[@]}"; do
    [[ "$e" == "$event" ]] && return 0
  done
  echo "ERROR: unknown hook event '$event'" >&2
  echo "  Valid events: ${_OC_VALID_EVENTS[*]}" >&2
  exit 1
}

# Print y/N prompt and return 0 (proceed) or 1 (decline).
# Respects CLAUDE_ONRAMP_AUTOCONFIRM=1 and CLAUDE_ONRAMP_DECLINE=1.
_oc_confirm() {
  if [[ "${CLAUDE_ONRAMP_AUTOCONFIRM:-0}" == "1" ]]; then
    return 0
  fi
  if [[ "${CLAUDE_ONRAMP_DECLINE:-0}" == "1" ]]; then
    return 1
  fi
  printf '\nProceed? [y/N] '
  read -r answer
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}
