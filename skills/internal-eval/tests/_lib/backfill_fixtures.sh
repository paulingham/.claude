#!/usr/bin/env bash
# Core fixtures + predicates for Story 4 tests. Scenarios in backfill_scenarios.sh.

grep_file()      { grep -qF "$2" "$1" 2>/dev/null; }
contains()       { printf '%s' "$1" | grep -qi "$2"; }
not_contains()   { ! contains "$1" "$2"; }
rc_eq()          { [ "$1" = "$2" ]; }
rc_ne()          { [ "$1" != "$2" ]; }
not_dir()        { [ ! -d "$1" ]; }
has_patch_file() { ls "$1/golden-diff/"*.patch >/dev/null 2>&1; }
has_candidate_dir()   { find "$1/eval/cases/.candidates" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | grep -q .; }
has_exclusion_report(){ find "$1/eval/.candidates" -name '.exclusion-report-*.md' 2>/dev/null | grep -q .; }

slug_eq() {
  local script="$1" in="$2" want="$3" got
  got="$(bash "$script" "$in")"; [ "$got" = "$want" ]
}

make_tmp_workdir() {
  local src="$1" d; d="$(mktemp -d)"
  mkdir -p "$d/eval/cases/.candidates" "$d/eval/.candidates"
  cp -r "$src/skills" "$d/" 2>/dev/null || true; printf '%s' "$d"
}

write_gh_shim() {
  local dir="$1" tests="$2"; mkdir -p "$dir/bin" "$dir/fixtures"
  cp "$tests/_mocks/gh" "$dir/bin/gh"; chmod +x "$dir/bin/gh"
  cp "$tests/_mocks/fixtures/"*.* "$dir/fixtures/" 2>/dev/null || true
}

valid_metadata_json() {
  printf '%s\n' '{"case_id":"test","classification":"feature","source_pr":"","min_harness_ref":"0","max_harness_ref":null,"flakiness_tier":"deterministic","scoring_mode":"test-passing","timeout_minutes":30,"cost_ceiling_usd":5,"synthetic":false}'
}

mk_candidate() {
  local d="$1"; mkdir -p "$d/context" "$d/golden-diff"
  echo "# task" > "$d/task.md"; echo "# expected" > "$d/expected.md"
  echo "--- diff ---" > "$d/golden-diff/pr-1.patch"
  valid_metadata_json > "$d/metadata.json"
}

source "$(dirname "${BASH_SOURCE[0]}")/backfill_scenarios.sh"
