#!/usr/bin/env bash
# Promote scenarios. Functions ≤ 8 lines.

_promote_rc() {
  local cap="$1" tmp="$2" cid="$3" rc=0
  (cd "$tmp" && bash "$cap/promote.sh" "$cid" >/dev/null 2>&1) || rc=$?
  printf '%s' "$rc"
}

run_promote_happy() {
  local cap="$1" tmp="$2" cid="happy-case-pr1" src="$2/eval/cases/.candidates/happy-case-pr1"
  mk_candidate "$src"; _promote_rc "$cap" "$tmp" "$cid" >/dev/null
  assert "promote: candidate moved" is_dir  "$tmp/eval/cases/$cid"
  assert "promote: source gone"     not_dir "$src"
}

run_promote_dest_exists() {
  local cap="$1" tmp="$2" cid="conflict-pr2" src="$2/eval/cases/.candidates/conflict-pr2" rc
  mk_candidate "$src"; mkdir -p "$tmp/eval/cases/$cid"
  rc="$(_promote_rc "$cap" "$tmp" "$cid")"
  assert "promote: dest exists → rc≠0" rc_ne "$rc" "0"
}

run_promote_bad_metadata() {
  local cap="$1" tmp="$2" cid="bad-meta-pr3" src="$2/eval/cases/.candidates/bad-meta-pr3" rc
  mk_candidate "$src"; echo "{ not valid" > "$src/metadata.json"
  rc="$(_promote_rc "$cap" "$tmp" "$cid")"
  assert "promote: bad metadata → rc≠0" rc_ne "$rc" "0"
  assert "promote: source preserved"    is_dir "$src"
}

run_promote_source_missing() {
  local cap="$1" tmp="$2" rc
  rc="$(_promote_rc "$cap" "$tmp" "missing-pr99")"
  assert "promote: source missing → rc≠0" rc_ne "$rc" "0"
}
