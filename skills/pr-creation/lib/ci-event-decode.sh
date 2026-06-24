#!/usr/bin/env bash
# ci-event-decode.sh — Thin event-line classifier for the Monitor event stream.
#
# Reads ONE structured event line from stdin and emits a classification token:
#   candidate-green  → well-formed line, all-SUCCESS conclusion, conclusion + sha present
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

  # WHY: parse AND classify inside a single python3 process — never round-trip
  # structured fields through newline-delimited text. A JSON value containing
  # a literal newline would split across lines and corrupt sed-based re-extraction,
  # allowing a crafted conclusion to spoof sha and produce false candidate-green.
  # Any field containing a control character (including newline, NUL) exits 2.
  echo "$line" | python3 -c "
import sys, json

try:
    d = json.load(sys.stdin)
except Exception:
    print('unevaluable: malformed-json', file=sys.stderr)
    sys.exit(2)

conclusion = d.get('conclusion', '')
sha = d.get('sha', '')

if not isinstance(conclusion, str) or not conclusion:
    print('unevaluable: missing-conclusion-field', file=sys.stderr)
    sys.exit(2)

if not isinstance(sha, str) or not sha:
    print('unevaluable: missing-sha-field', file=sys.stderr)
    sys.exit(2)

for name, val in (('conclusion', conclusion), ('sha', sha)):
    if any(ord(c) < 0x20 for c in val):
        print(f'unevaluable: control-char-in-{name}', file=sys.stderr)
        sys.exit(2)

RED = {'FAILURE', 'ERROR', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED', 'STARTUP_FAILURE'}
if conclusion == 'SUCCESS':
    print('candidate-green')
elif conclusion in RED:
    print('RED-hint')
else:
    print(f'unevaluable: unknown-conclusion:{conclusion}', file=sys.stderr)
    sys.exit(2)
"
}

_decode_event
