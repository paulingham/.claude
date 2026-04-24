#!/usr/bin/env bash
# Parses a baseline markdown file into JSON for diff consumption.
# Extracts frontmatter key/value pairs + the per-case table rows.

# parse_baseline_json <baseline.md> → stdout: {harness_ref, cases: [{case_id, status}]}
parse_baseline_json() {
  local file="$1"
  local harness; harness="$(_grep_fm "$file" harness_ref)"
  jq -Rn --arg h "$harness" --arg raw "$(_case_rows "$file")" \
    '{harness_ref:$h, cases: ($raw|split("\n")|map(select(length>0)|split("|")
      |{case_id:(.[1]|ltrimstr(" ")|rtrimstr(" ")),
        status:(.[2]|ltrimstr(" ")|rtrimstr(" "))}))}'
}

_grep_fm() {
  sed -n "s/^$2: *\(.*\)$/\1/p" "$1" | head -1
}

_case_rows() {
  awk '/^\| *case_id */{next} /^\|---/{next} /^\|/{print}' "$1"
}
