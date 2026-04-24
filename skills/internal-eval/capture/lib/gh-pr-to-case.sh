#!/usr/bin/env bash
# PR → case artifacts. Delegates artifact writers to case-writers.sh.
HERE_GPC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE_GPC/slug_fn.sh"
source "$HERE_GPC/meta.sh"
source "$HERE_GPC/case-writers.sh"

pr_view_json()  { gh pr view "$1" --json number,title,body,labels,mergeCommit 2>/dev/null; }
pr_diff_patch() { gh pr diff "$1" 2>/dev/null; }
pr_diff_names() { gh pr diff "$1" --name-only 2>/dev/null; }

case_id_for() {
  local pr="$1" slug
  slug="$(slugify "$2")"
  printf '%s-pr%s' "$slug" "$pr"
}

_extract_fields() {
  local view="$1"
  jq -r '.title, .body, (.mergeCommit.oid // "")' <<<"$view"
}

gh_pr_to_case() {
  local pr="$1" outbase="$2" view names cid out title body sha
  view="$(pr_view_json "$pr")"; [ -z "$view" ] && return 1
  { read -r title; read -r body; read -r sha; } < <(_extract_fields "$view")
  names="$(pr_diff_names "$pr")"
  cid="$(case_id_for "$pr" "$title")"; out="$outbase/$cid"
  mkdir -p "$out"
  write_all_artifacts "$pr" "$view" "$title" "$body" "$names" "$sha" "$cid" "$out"
  printf '%s\n' "$cid"
}
