#!/usr/bin/env bash
# /internal-eval capture promote <case-id>
# Atomically moves a candidate into the active suite.
set -u

_fail() { echo "promote: $1" >&2; exit 1; }

_require_source() {
  local src="$1"
  [ -d "$src" ] || _fail "candidate missing: $src"
}

_require_no_dest() {
  local dest="$1"
  [ ! -e "$dest" ] || _fail "destination already exists: $dest"
}

_validate_metadata() {
  local src="$1" meta="$src/metadata.json"
  [ -f "$meta" ]                       || _fail "metadata.json missing in $src"
  jq -e . "$meta" >/dev/null 2>&1      || _fail "metadata.json invalid JSON in $src"
  jq -e '.case_id and .classification and .flakiness_tier' "$meta" >/dev/null 2>&1 \
    || _fail "metadata.json missing required fields"
}

promote_case() {
  local cid src dest
  cid="$1"; src="eval/cases/.candidates/$cid"; dest="eval/cases/$cid"
  _require_source "$src"; _require_no_dest "$dest"; _validate_metadata "$src"
  mv "$src" "$dest"
  echo "promoted: $cid"
}

[ "$#" -eq 1 ] || { echo "usage: promote.sh <case-id>" >&2; exit 2; }
promote_case "$1"
