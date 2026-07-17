#!/usr/bin/env bash
# Phase A three-gear classifier — the "when" half of the gear architecture.
# Reads {"prompt": "..."} on stdin, echoes PAIR|BUILD|PIPELINE, and mirrors
# the choice to session state the same way the statusline bridges ctx-percent.
#
# Polarity is INVERTED vs the legacy T0-T6 fingerprint: default is the
# lightest gear (PAIR), escalating only on positive evidence. A gate that
# cannot evaluate its input (empty/malformed prompt) fails to the heaviest
# gear (PIPELINE) — fail SAFE means fail HEAVY here, never silently light.
#
# WHY jq-free: this runs on every prompt, so it must not add a hard runtime
# dependency to the hot path; grep/sed extraction keeps it self-contained.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/state-dir.sh"

_gear_select_extract_prompt() {
  # Pulls the value of a top-level "prompt" JSON string key without jq.
  # Deliberately conservative: only handles a simple single-line string
  # value (the shape the harness actually emits). Anything else -> empty,
  # which the caller treats as an unevaluable/fail-safe input.
  local json="$1"
  local extracted
  extracted=$(printf '%s' "$json" | grep -o '"prompt"[[:space:]]*:[[:space:]]*"\([^"\\]\|\\.\)*"' | head -1)
  [[ -z "$extracted" ]] && return 1
  extracted="${extracted#*:}"
  extracted="${extracted#"${extracted%%[![:space:]]*}"}"  # ltrim
  extracted="${extracted#\"}"
  extracted="${extracted%\"}"
  printf '%s' "$extracted"
}

_gear_select_has_override() {
  local prompt_lower="$1"
  if [[ "$prompt_lower" =~ (just[[:space:]]pair|pair[[:space:]]on[[:space:]]this) ]]; then
    printf 'PAIR'; return 0
  fi
  if [[ "$prompt_lower" =~ (ship[[:space:]]it[[:space:]]properly|take[[:space:]]it[[:space:]]all[[:space:]]the[[:space:]]way|full[[:space:]]pipeline) ]]; then
    printf 'PIPELINE'; return 0
  fi
  if [[ "$prompt_lower" =~ (build[[:space:]]it([[:space:]]|,|\.|$)|build[[:space:]]this[[:space:]]properly) ]]; then
    printf 'BUILD'; return 0
  fi
  return 1
}

_gear_select_classify() {
  local prompt_lower="$1"
  if [[ "$prompt_lower" =~ (auth|token|secret|payment|crypto|password|session|billing|oauth|jwt|migration|schema|cross-repo|multi-repo|critical) ]]; then
    printf 'PIPELINE'; return 0
  fi
  if [[ "$prompt_lower" =~ (build|implement|add|create|refactor|migrate).*(feature|endpoint|component|service|caching|layer|dashboard) ]] \
    || [[ "$prompt_lower" =~ (new[[:space:]]endpoint|new[[:space:]]component|new[[:space:]]feature) ]] \
    || [[ "$prompt_lower" =~ (three|multiple|several)[[:space:]]files ]]; then
    printf 'BUILD'; return 0
  fi
  printf 'PAIR'
}

_gear_select_persist() {
  local gear="$1"
  _ensure_state_dir 2>/dev/null || return 0
  printf '%s\n' "$gear" | _state_write "gear-${PPID}" 2>/dev/null || true
}

gear_select() {
  local input gear prompt
  input=$(cat 2>/dev/null) || { printf 'PIPELINE'; return 0; }
  if [[ -z "$input" ]]; then
    printf 'PIPELINE'
    return 0
  fi

  prompt=$(_gear_select_extract_prompt "$input") || { printf 'PIPELINE'; return 0; }
  if [[ -z "$prompt" ]]; then
    printf 'PIPELINE'
    return 0
  fi

  local prompt_lower
  prompt_lower=$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')

  gear=$(_gear_select_has_override "$prompt_lower") || gear=$(_gear_select_classify "$prompt_lower")

  _gear_select_persist "$gear"
  printf '%s' "$gear"
}
