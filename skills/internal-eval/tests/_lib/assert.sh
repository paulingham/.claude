#!/usr/bin/env bash
# Minimal TAP-ish assertion helpers. Callers set PASS / FAIL counters.
assert() {
  local msg="$1"; shift
  if "$@"; then PASS=$((PASS+1)); echo "ok - $msg"; else FAIL=$((FAIL+1)); echo "not ok - $msg"; fi
}

is_file()     { [ -f "$1" ]; }
is_dir()      { [ -d "$1" ]; }
is_ignored()  { (cd "$1" && git check-ignore -q "$2"); }
not_ignored() { ! is_ignored "$1" "$2"; }
json_valid()  { jq -e . "$1" >/dev/null 2>&1; }
json_has()    { jq -e --arg k "$2" 'has($k)' "$1" >/dev/null 2>&1; }
