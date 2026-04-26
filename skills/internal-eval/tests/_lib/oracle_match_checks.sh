#!/usr/bin/env bash
# Unit-level tests for oracle_match_paths exclude semantics.

_oracle_fixture() {
  printf '%s' '{"include":["docs/**"],"exclude":["**/*.md"]}' >"$1"
}

_oracle_rc() {
  ( source "$1/lib/oracle-match.sh"; oracle_match_paths "$2" "$3"; echo $?; ) | tail -1
}

check_oracle_exclude() {
  local cap="$1" tmp json; tmp="$(mktemp -d)"; json="$tmp/o.json"; _oracle_fixture "$json"
  assert "exclude overrides include"       rc_eq "$(_oracle_rc "$cap" "$json" "docs/a.md")"   "1"
  assert "non-excluded path still matches" rc_eq "$(_oracle_rc "$cap" "$json" "docs/a.bats")" "0"
  rm -rf "$tmp"
}
