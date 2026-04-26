#!/usr/bin/env bash
# Metadata JSON assembly for captured cases. Functions ≤ 5 lines.

_infer_classification() {
  local labels="$1" title="$2"
  printf '%s\n' "$labels" | grep -qiE 'bug|fix'  && { echo bug-fix;   return; }
  printf '%s\n' "$labels" | grep -qiE 'feat'     && { echo feature;   return; }
  printf '%s\n' "$labels" | grep -qiE 'refactor' && { echo refactor;  return; }
  printf '%s' "$title" | grep -qiE '^(fix|bug)'  && { echo bug-fix;   return; }
  echo feature
}

_pr_url() {
  local n="$1" remote
  remote="$(git remote get-url origin 2>/dev/null | sed 's/\.git$//; s|git@github.com:|https://github.com/|')"
  [ -z "$remote" ] && remote="https://github.com/unknown/unknown"
  printf '%s/pull/%s' "$remote" "$n"
}

_min_ref() {
  git -C "$HOME/.claude" rev-parse HEAD 2>/dev/null \
    || git rev-parse HEAD 2>/dev/null \
    || echo "0000000000000000000000000000000000000000"
}

_meta_field() { printf '%s' "$1" | jq -r "$2"; }

write_metadata() {
  local view pr cid out labels title cls url ref
  view="$1"; pr="$2"; cid="$3"; out="$4"
  labels="$(_meta_field "$view" '[.labels[].name] | join(",")')"
  title="$(_meta_field "$view" '.title')"; cls="$(_infer_classification "$labels" "$title")"
  url="$(_pr_url "$pr")"; ref="$(_min_ref)"
  jq -n --arg id "$cid" --arg c "$cls" --arg u "$url" --arg r "$ref" \
    '{case_id:$id,classification:$c,source_pr:$u,min_harness_ref:$r,max_harness_ref:null,flakiness_tier:"deterministic",scoring_mode:"test-passing",timeout_minutes:30,cost_ceiling_usd:5,synthetic:false}' > "$out"
}
