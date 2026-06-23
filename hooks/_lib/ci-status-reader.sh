#!/usr/bin/env bash
# ci-status-reader.sh — Fail-closed CI-status decision for the CI-green gate.
#
# Exposes: ci_status_decision <pr-number>
#   return 0 = ALLOW (CI conclusively green)
#   return 2 = BLOCK (any red/pending/error/unknown/unevaluable state)
#
# Fail-closed: every path except an explicit all-SUCCESS rollup → BLOCK (2).
# Mirrors the is-protected-path.sh fail-closed pattern:
#   - Source guard to allow safe multiple-source
#   - Capture-then-test for piped commands (pipefail-safe)
#   - Error-vs-absent distinction (gh-error vs empty-rollup)
#   - Unconditional final BLOCK (the ONE allow path is all-green)
#
# C2 status map — conclusion drives the decision:
#   non-empty rollup AND all conclusion==SUCCESS/NEUTRAL        → ALLOW (0)
#   ANY FAILURE/CANCELLED/TIMED_OUT/ACTION_REQUIRED             → BLOCK (2)
#   ANY PENDING/EXPECTED/IN_PROGRESS/QUEUED/state==PENDING      → BLOCK (2)
#   ANY ERROR                                                   → BLOCK (2)
#   ANY SKIPPED                                                 → BLOCK (2)
#   conclusion empty (legacy StatusContext) → state is authority:
#     state==SUCCESS/NEUTRAL                                    → ALLOW (0)
#     state==FAILURE/ERROR/etc                                  → BLOCK (2)
#     state empty (both empty)                                  → BLOCK (2)
#   empty/null rollup                                           → BLOCK (2)
#   gh non-zero / auth error / network error                   → BLOCK (2)
#   jq parse error / malformed JSON                            → BLOCK (2)
#   missing/empty PR number or fails ^[0-9]+$                  → BLOCK (2)
#   unknown status token                                        → BLOCK (2)
#
# Default branch: BLOCK. ALLOW is reachable on exactly one path.
#
# Source guard — safe to source multiple times:
[[ -n "${_CI_STATUS_READER_LOADED:-}" ]] && return
_CI_STATUS_READER_LOADED=1

# _csr_validate_pr: exit 2 if PR number is missing or non-numeric.
# WHY: prevent shell injection before any interpolation into gh commands.
_csr_validate_pr() {
  local pr="${1:-}"
  [[ -z "$pr" ]] && return 2
  [[ "$pr" =~ ^[0-9]+$ ]] || return 2
  return 0
}

# _csr_fetch_rollup: capture gh output and rc, then test.
# Sets _CSR_GH_OUTPUT and _CSR_GH_RC in caller scope.
# WHY: capture-then-test avoids pipefail swallowing gh's non-zero exit.
_csr_fetch_rollup() {
  local pr="$1"
  _CSR_GH_OUTPUT="$(gh pr view "$pr" --json statusCheckRollup 2>&1)"
  _CSR_GH_RC=$?
}

# _csr_extract_rollup: parse JSON with jq, return the rollup array as JSON.
# Sets _CSR_ROLLUP_JSON and _CSR_JQ_RC in caller scope.
_csr_extract_rollup() {
  local raw="$1"
  _CSR_ROLLUP_JSON="$(printf '%s' "$raw" | jq -r '.statusCheckRollup' 2>/dev/null)"
  _CSR_JQ_RC=$?
}

# _csr_sanitize_token: strip non-printable chars, cap at 32 alnum/-/_ chars.
# WHY: raw GitHub status enum tokens go into log/reason strings; sanitize for
# log hygiene (not a security vulnerability — never executed, not a secret).
_csr_sanitize_token() {
  printf '%s' "${1:-}" | tr -cd 'a-zA-Z0-9_-' | cut -c1-32
}

# _csr_check_entry: map a single check entry (conclusion + state fields).
# Prints "ALLOW" or "BLOCK:<reason>".
#
# Decision authority:
#   - When conclusion is non-empty: conclusion drives the decision;
#     state can only TIGHTEN (never loosen) a passing conclusion.
#   - When conclusion is empty (legacy StatusContext): state is the authority.
#   - When both are empty: BLOCK (unknown/unevaluable — fail-closed).
_csr_check_entry() {
  local conclusion="$1" state="$2"

  case "$conclusion" in
    SUCCESS|NEUTRAL) ;;
    FAILURE|CANCELLED|TIMED_OUT|ACTION_REQUIRED)
      printf 'BLOCK:failure' ; return ;;
    PENDING|EXPECTED|IN_PROGRESS|QUEUED)
      printf 'BLOCK:pending' ; return ;;
    ERROR)
      printf 'BLOCK:error' ; return ;;
    SKIPPED)
      printf 'BLOCK:skipped' ; return ;;
    "")
      # WHY: conclusion empty = legacy StatusContext (GitHub status API, not
      # CheckRun API). The state field is the authority for these entries.
      # Empty conclusion AND empty state → BLOCK (unknown/unevaluable).
      case "$state" in
        SUCCESS|NEUTRAL)
          printf 'ALLOW' ; return ;;
        FAILURE|CANCELLED|TIMED_OUT|ACTION_REQUIRED)
          printf 'BLOCK:failure' ; return ;;
        PENDING|EXPECTED|IN_PROGRESS|QUEUED)
          printf 'BLOCK:pending' ; return ;;
        ERROR)
          printf 'BLOCK:error' ; return ;;
        SKIPPED)
          printf 'BLOCK:skipped' ; return ;;
        *)
          local _safe_state
          _safe_state="$(_csr_sanitize_token "$state")"
          printf "BLOCK:unknown-check-type:%s" "$_safe_state" ; return ;;
      esac ;;
    *)
      local _safe_conclusion
      _safe_conclusion="$(_csr_sanitize_token "$conclusion")"
      printf "BLOCK:unknown-check-type:%s" "$_safe_conclusion" ; return ;;
  esac

  # conclusion is SUCCESS|NEUTRAL — also check legacy state field to tighten.
  # WHY: a CheckRun may carry both fields; a non-passing state can only tighten.
  # Empty state here means the state field is absent/irrelevant → pass through.
  case "$state" in
    SUCCESS|NEUTRAL|"") ;;
    PENDING|EXPECTED|IN_PROGRESS|QUEUED)
      printf 'BLOCK:pending' ; return ;;
    FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|SKIPPED)
      printf 'BLOCK:failure' ; return ;;
    *)
      local _safe_state2
      _safe_state2="$(_csr_sanitize_token "$state")"
      printf "BLOCK:unknown-check-type:%s" "$_safe_state2" ; return ;;
  esac

  printf 'ALLOW'
}

# _csr_evaluate_rollup: iterate over rollup entries; return first BLOCK or ALLOW.
# Prints a decision token: "ALLOW" or "BLOCK:<reason>".
_csr_evaluate_rollup() {
  local rollup_json="$1"
  local length conclusion state decision

  # Empty or null rollup → BLOCK
  if [[ "$rollup_json" == "null" ]] || [[ "$rollup_json" == "[]" ]] || [[ -z "$rollup_json" ]]; then
    printf 'BLOCK:empty-rollup'
    return
  fi

  length="$(printf '%s' "$rollup_json" | jq 'length' 2>/dev/null)"
  if [[ -z "$length" ]] || [[ "$length" == "0" ]]; then
    printf 'BLOCK:empty-rollup'
    return
  fi

  local i=0
  while [[ $i -lt $length ]]; do
    conclusion="$(printf '%s' "$rollup_json" | jq -r ".[$i].conclusion // empty" 2>/dev/null)"
    state="$(printf '%s' "$rollup_json" | jq -r ".[$i].state // empty" 2>/dev/null)"
    decision="$(_csr_check_entry "$conclusion" "$state")"
    if [[ "$decision" != "ALLOW" ]]; then
      printf '%s' "$decision"
      return
    fi
    i=$((i + 1))
  done

  # All entries checked and passed → ALLOW
  printf 'ALLOW'
}

# ci_status_decision <pr-number>: main entry point.
# return 0 = ALLOW, return 2 = BLOCK.
# Sets _CSR_REASON on BLOCK so callers can emit human-readable messages.
ci_status_decision() {
  local pr="${1:-}"
  _CSR_REASON=""

  # C3: validate PR number before any interpolation
  if ! _csr_validate_pr "$pr"; then
    _CSR_REASON="invalid-pr-number"
    return 2
  fi

  # Fetch CI status — capture-then-test (is-protected-path.sh:138-140 pattern)
  _csr_fetch_rollup "$pr"
  if [[ $_CSR_GH_RC -ne 0 ]]; then
    _CSR_REASON="gh-error"
    return 2
  fi

  # Parse JSON — capture-then-test
  _csr_extract_rollup "$_CSR_GH_OUTPUT"
  if [[ $_CSR_JQ_RC -ne 0 ]]; then
    _CSR_REASON="malformed-json"
    return 2
  fi

  # Evaluate rollup entries
  local decision
  decision="$(_csr_evaluate_rollup "$_CSR_ROLLUP_JSON")"

  if [[ "$decision" == "ALLOW" ]]; then
    _CSR_REASON=""
    return 0
  fi

  # Extract reason from decision token (format: BLOCK:<reason>)
  _CSR_REASON="${decision#BLOCK:}"

  # Unconditional final BLOCK — the only path that doesn't reach here is ALLOW above.
  # WHY: Iron Law 8 — the gate fails closed; any unrecognized state falls through here.
  return 2
}
