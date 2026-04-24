#!/usr/bin/env bash
# Suite enumeration: expand --suite default to list of case-ids.
# default = eval/cases/* excluding _example and .candidates.

# enumerate_cases <suite> <cases-dir>  -- prints case-ids one per line.
enumerate_cases() {
  local suite="$1"; local cases_dir="$2"
  [ "$suite" = "default" ] || { echo "$suite"; return; }
  _enumerate_default "$cases_dir"
}

_enumerate_default() {
  find "$1" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
    | _basename_each \
    | grep -v '^_example$\|^\.candidates$' || true
}

_basename_each() { while IFS= read -r p; do basename "$p"; done; }
