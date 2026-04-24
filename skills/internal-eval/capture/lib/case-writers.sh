#!/usr/bin/env bash
# Per-artifact writers for a captured case. Each function body ≤ 5 lines.

_esc_re() { printf '%s' "$1" | sed 's/[][\/.*^$]/\\&/g'; }

strip_file_refs() {
  local body="$1" names="$2" f esc
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    esc="$(_esc_re "$f")"; body="$(printf '%s' "$body" | sed "s|$esc||g")"
  done <<<"$names"
  printf '%s' "$body"
}

write_task_md() {
  local title="$1" body="$2" names="$3" out="$4"
  printf '# %s\n\n%s\n' "$title" "$(strip_file_refs "$body" "$names")" > "$out/task.md"
}

_test_files() { printf '%s\n' "$1" | grep -Ei '(tests?/|_test\.|_spec\.|\.test\.)' || echo "(none detected)"; }

write_expected_md() {
  local names="$1" body="$2" out="$3"
  { printf '# Expected Outcomes\n\n## Test files changed\n'; _test_files "$names"
    printf '\n## Qualitative outcomes\n\n%s\n' "$body"; } > "$out/expected.md"
}

write_golden_diff() {
  local pr="$1" out="$2"; mkdir -p "$out/golden-diff"
  pr_diff_patch "$pr" > "$out/golden-diff/pr-${pr}.patch"
}

_restore_file() {
  local f="$1" out="$2" sha="$3"
  mkdir -p "$out/context/$(dirname "$f")" 2>/dev/null || true
  git show "${sha}^:$f" > "$out/context/$f" 2>/dev/null || true
}

write_context() {
  local names="$1" out="$2" sha="$3" f; mkdir -p "$out/context"
  while IFS= read -r f; do [ -z "$f" ] && continue; _restore_file "$f" "$out" "$sha"; done <<<"$names"
}

write_all_artifacts() {
  local pr="$1" view="$2" title="$3" body="$4" names="$5" sha="$6" cid="$7" out="$8"
  write_task_md "$title" "$body" "$names" "$out"
  write_expected_md "$names" "$body" "$out"
  write_golden_diff "$pr" "$out"; write_context "$names" "$out" "$sha"
  write_metadata "$view" "$pr" "$cid" "$out/metadata.json"
}
