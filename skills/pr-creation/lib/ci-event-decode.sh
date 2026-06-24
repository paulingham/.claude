#!/usr/bin/env bash
# ci-event-decode.sh — Thin event-line classifier for the Monitor event stream.
#
# Reads ONE structured event line from stdin and emits a classification token:
#   candidate-green  → well-formed line, all-SUCCESS conclusion, sha + pr present
#   RED-hint         → well-formed line with FAILURE/ERROR conclusion
#   exit 2 + reason  → unevaluable: malformed/empty/absent/missing-field
#
# MUST NOT reimplement rollup fail-closed logic.
# MUST NOT emit CI_GREEN — GREEN authority stays with ci_status_decision(PR).
# Iron Law 8: any unevaluable input exits 2. Never silently proceed as green.
#
# SIGTERM/INT: trap and exit 2 so a Monitor subscription kill does not
# leave the caller in an ambiguous (exit 0) state.
set -euo pipefail
trap 'exit 2' INT TERM

_decode_event() {
  local line
  line="$(cat)"

  if [[ -z "$line" ]]; then
    echo "unevaluable: empty-input" >&2
    exit 2
  fi

  local conclusion sha pr parsed
  parsed="$(echo "$line" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('conclusion',''))
    print(d.get('sha',''))
    print(d.get('pr',''))
except Exception:
    sys.exit(1)
" 2>/dev/null)" || parsed=""
  conclusion="$(echo "$parsed" | sed -n '1p')"
  sha="$(echo "$parsed" | sed -n '2p')"
  pr="$(echo "$parsed" | sed -n '3p')"

  if [[ -z "$conclusion" ]]; then
    echo "unevaluable: missing-conclusion-field" >&2
    exit 2
  fi

  if [[ -z "$sha" ]]; then
    echo "unevaluable: missing-sha-field" >&2
    exit 2
  fi

  case "$conclusion" in
    SUCCESS)
      # Authoritative GREEN decision deferred to ci_status_decision(PR).
      # This decoder classifies only — never decides final green.
      echo "candidate-green"
      ;;
    FAILURE|ERROR|CANCELLED|TIMED_OUT|ACTION_REQUIRED|STARTUP_FAILURE)
      echo "RED-hint"
      ;;
    *)
      # WHY: Iron Law 8 — unknown/unevaluable conclusion fails closed, never allows.
      echo "unevaluable: unknown-conclusion:${conclusion}" >&2
      exit 2
      ;;
  esac
}

_decode_event
