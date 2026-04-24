#!/usr/bin/env bash
# Stage + fixture-writer helpers. Runners live in eval_capture_runners.sh.
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_fixtures.sh"
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_runners.sh"

_stage_gh_shim() {
  local tmp="$1" root="$2"; mkdir -p "$tmp/bin"
  cp "$root/skills/internal-eval/tests/_mocks/gh" "$tmp/bin/gh"
  chmod +x "$tmp/bin/gh"
}

_stage_fixtures_dir() {
  local tmp="$1" root="$2"; mkdir -p "$tmp/fixtures"
  cp "$root/skills/internal-eval/tests/_mocks/fixtures/"*.* "$tmp/fixtures/" 2>/dev/null || true
}

_prep_worker_env() {
  local tmp="$1" root="$2"
  _stage_gh_shim "$tmp" "$root"; _stage_fixtures_dir "$tmp" "$root"
  mkdir -p "$tmp/skills/internal-eval/capture"
  cp -r "$root/skills/internal-eval/capture/"* "$tmp/skills/internal-eval/capture/" 2>/dev/null || true
}

_write_fixture_old_merge() {
  local dir="$1" pr="$2"; mkdir -p "$dir"
  printf '{"number":%s,"title":"Old","body":"b","labels":[],"mergeCommit":{"oid":"a"},"mergedAt":"2025-12-01T00:00:00Z"}\n' \
    "$pr" > "$dir/oldpr-pr${pr}-view.json"
  printf 'src/foo.ts\ntests/foo.test.ts\n' > "$dir/oldpr-pr${pr}-names.txt"
}
