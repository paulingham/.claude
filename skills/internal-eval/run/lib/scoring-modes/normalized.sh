#!/usr/bin/env bash
# Normalized scoring: whitespace/blank-line insensitive compare.
# Preserves semantic content and line order; collapses runs of whitespace,
# strips trailing whitespace, and drops blank lines.

_normalize_stream() {
  sed -e 's/[[:space:]]\{1,\}/ /g' -e 's/[[:space:]]*$//' -e '/^$/d' "$1"
}

# score_normalized <golden> <candidate> → rc 0 if normalized streams match.
score_normalized() {
  diff -q <(_normalize_stream "$1") <(_normalize_stream "$2") >/dev/null
}
