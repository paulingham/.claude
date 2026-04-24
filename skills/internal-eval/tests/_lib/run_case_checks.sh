#!/usr/bin/env bash
# Test helpers for Story 6 run-case.sh. Each check function performs a
# single focused assertion; keeps the test runner thin.

REQUIRED_RESULT_KEYS="case_id run_id status duration_sec cost_usd review_rounds rework harness_ref model flakiness_tier scoring_mode timestamp inner_pipeline_state failure_reason"
FIXTURE=""

check_result_writer() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  local tmp; tmp="$(mktemp -d)"
  write_result_json "$tmp/result.json" case=c1 run=r1 status=passed \
    duration=12.5 cost=0.0 rounds=0 rework=false harness=live model=opus \
    flakiness=deterministic scoring=test-passing ts=2026-04-24T00:00:00Z \
    inner="$tmp/inner" reason=""
  assert "write_result_json: file exists"            is_file "$tmp/result.json"
  assert "write_result_json: valid JSON"             json_valid "$tmp/result.json"
  for k in $REQUIRED_RESULT_KEYS; do
    assert "write_result_json: has key $k"           json_has "$tmp/result.json" "$k"
  done
  rm -rf "$tmp"
}

check_pass_status() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  local stub="$tmp/pass.sh"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$stub"; chmod +x "$stub"
  EVAL_RUNS_DIR="$tmp" EVAL_INNER_STUB="$stub" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rpass --timeout 5 >/dev/null
  local result="$tmp/rpass/cases/per-project-instincts-bootstrap-pr19/result.json"
  assert "pass: status = passed" _eq "$(jq -r .status "$result")" "passed"
  assert "pass: attempts=1 emitted by default" _eq "$(jq -r .attempts "$result")" 1
  rm -rf "$tmp"
}

check_infra_failure() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  EVAL_CLAUDE_BIN="$tmp/nonexistent-claude-bin" EVAL_RUNS_DIR="$tmp" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rinfra --timeout 5 >/dev/null 2>&1
  local result="$tmp/rinfra/cases/per-project-instincts-bootstrap-pr19/result.json"
  assert "infra: claude bin missing → failed_infra" \
    _eq "$(jq -r .status "$result")" "failed_infra"
  rm -rf "$tmp"
}

check_real_dispatch() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  _write_fake_claude "$tmp/claude" "$tmp/claude.log"
  env -i PATH="$PATH" HOME="$HOME" EVAL_CLAUDE_BIN="$tmp/claude" EVAL_RUNS_DIR="$tmp" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rreal --timeout 10 >/dev/null
  local result="$tmp/rreal/cases/per-project-instincts-bootstrap-pr19/result.json"
  assert "real dispatch: result status = passed" _eq "$(jq -r .status "$result")" "passed"
  assert "real dispatch: claude binary was invoked" is_file "$tmp/claude.log"
  assert "real dispatch: invoked with /pipeline prefix" _grep "$tmp/claude.log" "/pipeline"
  assert "real dispatch: inner EVAL_INNER_STUB cleared" _grep "$tmp/claude.log" "STUB_EMPTY=1"
  assert "real dispatch: CLAUDE_PIPELINE_BYPASS=1 exported" _grep "$tmp/claude.log" "BYPASS=1"
  assert "real dispatch: CLAUDE_DISABLE_AUTO_LEARN=1 exported" _grep "$tmp/claude.log" "NOLEARN=1"
  assert "real dispatch: EVAL_RUN_ID exported" _grep "$tmp/claude.log" "RUN=rreal"
  rm -rf "$tmp"
}

_write_fake_claude() {
  local bin="$1"; local log="$2"
  cat > "$bin" <<EOF
#!/usr/bin/env bash
echo "args=\$*" > "$log"
[ -z "\${EVAL_INNER_STUB:-}" ] && echo "STUB_EMPTY=1" >> "$log"
[ "\${CLAUDE_PIPELINE_BYPASS:-}" = "1" ] && echo "BYPASS=1" >> "$log"
[ "\${CLAUDE_DISABLE_AUTO_LEARN:-}" = "1" ] && echo "NOLEARN=1" >> "$log"
[ -n "\${EVAL_RUN_ID:-}" ] && echo "RUN=\$EVAL_RUN_ID" >> "$log"
exit 0
EOF
  chmod +x "$bin"
}

check_timeout_status() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  local stub="$tmp/slow.sh"
  printf '#!/usr/bin/env bash\nsleep 10\n' > "$stub"; chmod +x "$stub"
  EVAL_RUNS_DIR="$tmp" EVAL_INNER_STUB="$stub" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rto --timeout 1 >/dev/null
  local result="$tmp/rto/cases/per-project-instincts-bootstrap-pr19/result.json"
  assert "timeout: result.json exists"    is_file "$result"
  assert "timeout: status = failed_timeout" \
    _eq "$(jq -r .status "$result")" "failed_timeout"
  rm -rf "$tmp"
}

check_kill_midrun_cleanliness() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  local stub="$tmp/slow.sh"
  printf '#!/usr/bin/env bash\ntrap "" TERM\nsleep 30\n' > "$stub"; chmod +x "$stub"
  local outer="$root/pipeline-state"
  local before_hash; before_hash="$(_hash_dir "$outer")"
  EVAL_RUNS_DIR="$tmp" EVAL_INNER_STUB="$stub" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rkill --timeout 1 >/dev/null
  local after_hash; after_hash="$(_hash_dir "$outer")"
  assert "kill-midrun: outer pipeline-state unchanged" _eq "$before_hash" "$after_hash"
  assert_not "kill-midrun: no eval-* residue in outer" \
    _has_residue "$outer" "eval-rkill-"
  rm -rf "$tmp"
}

_hash_dir()    { (cd "$1" 2>/dev/null && find . -type f 2>/dev/null | LC_ALL=C sort | xargs md5sum 2>/dev/null | md5sum); }
_has_residue() { ls "$1"/*"$2"* >/dev/null 2>&1; }

check_inner_state_location() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  EVAL_RUNS_DIR="$tmp" bash "$run/run-case.sh" \
    --case-id per-project-instincts-bootstrap-pr19 --run-id rloc --dry-run >/dev/null
  local result="$tmp/rloc/cases/per-project-instincts-bootstrap-pr19/result.json"
  local inner; inner="$(jq -r .inner_pipeline_state "$result")"
  assert "inner state: path under eval run-dir" _matches "$inner" "$tmp/rloc/inner/"
  assert_not "inner state: path NOT under shared pipeline-state" \
    _matches "$inner" "/pipeline-state/"
  rm -rf "$tmp"
}

_matches() { case "$1" in *"$2"*) return 0 ;; *) return 1 ;; esac }

check_run_case_keys() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  EVAL_RUNS_DIR="$tmp" bash "$run/run-case.sh" \
    --case-id per-project-instincts-bootstrap-pr19 --run-id rkey --dry-run >/dev/null
  local result="$tmp/rkey/cases/per-project-instincts-bootstrap-pr19/result.json"
  for k in $REQUIRED_RESULT_KEYS; do
    assert "run-case result.json has key $k" json_has "$result" "$k"
  done
  rm -rf "$tmp"
}

check_dry_run() {
  local root="$1"; local run="$2"
  local tmp; tmp="$(mktemp -d)"
  EVAL_RUNS_DIR="$tmp" bash "$run/run-case.sh" \
    --case-id per-project-instincts-bootstrap-pr19 --run-id rdry --dry-run >/dev/null
  local result="$tmp/rdry/cases/per-project-instincts-bootstrap-pr19/result.json"
  assert "dry-run: result.json exists" is_file "$result"
  assert "dry-run: status = dry_run_ok" \
    _eq "$(jq -r .status "$result")" "dry_run_ok"
  assert_not "dry-run: did not create inner pipeline-state" \
    is_dir "$tmp/rdry/inner/per-project-instincts-bootstrap-pr19/pipeline-state"
  rm -rf "$tmp"
}

check_timeout() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/timeout.sh"
  assert "timeout: fast cmd succeeds"  run_with_timeout 2 true
  assert_not "timeout: slow cmd exits non-zero" run_with_timeout 1 sleep 5
  assert "timeout: exit 124 = timed out"  _eq "$(run_with_timeout 1 sleep 5; echo $?)" "124"
}

check_scoring_stub() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring.sh"
  assert "scoring: all gates green → passed" \
    _eq "$(score_case APPROVE APPROVE VERIFIED COVERED APPROVED)" "passed"
  assert "scoring: review CHANGES_REQUESTED → failed_diff" \
    _eq "$(score_case CHANGES_REQUESTED APPROVE VERIFIED COVERED APPROVED)" "failed_diff"
  assert "scoring: verify UNVERIFIED → failed_diff" \
    _eq "$(score_case APPROVE APPROVE UNVERIFIED COVERED APPROVED)" "failed_diff"
  assert "scoring: accept REJECTED → failed_diff" \
    _eq "$(score_case APPROVE APPROVE VERIFIED COVERED REJECTED)" "failed_diff"
}

check_harness_ref_failure() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  local tmp; tmp="$(mktemp -d)"; mkdir -p "$tmp/norepo"
  assert_not "harness-ref: bad sha → non-zero exit" \
    _call_resolve_with_bad_repo "$tmp/norepo" "$tmp/wt"
  rm -rf "$tmp"
}

_call_resolve_with_bad_repo() {
  CLAUDE_HARNESS_REPO="$1" resolve_harness_root "deadbeef" "$2" >/dev/null
}

check_harness_ref_pinned() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  FIXTURE="$(mktemp -d)"
  local sha; sha="$(_setup_harness_fixture "$FIXTURE")"
  local wt="$FIXTURE/wt"
  local root; root="$(CLAUDE_HARNESS_REPO="$FIXTURE/repo" resolve_harness_root "$sha" "$wt")"
  assert "harness-ref: pinned root = wt path" _eq "$root" "$wt"
  assert "harness-ref: pinned tree has marker v1" is_file "$root/marker-v1"
  assert_not "harness-ref: pinned tree lacks v2" is_file "$root/marker-v2"
  rm -rf "$FIXTURE"
}

_setup_harness_fixture() {
  local fx="$1"; mkdir -p "$fx/repo"
  (cd "$fx/repo" && git init -q && git config user.email t@t && git config user.name t \
    && touch marker-v1 && git add marker-v1 && git commit -q -m v1 \
    && git rev-parse HEAD > "$fx/sha1" \
    && touch marker-v2 && git add marker-v2 && git commit -q -m v2) >&2
  cat "$fx/sha1"
}

check_harness_ref() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  assert "harness-ref: live default sha" _eq "$(resolve_harness_sha "")" "live"
  assert "harness-ref: live default root" _eq "$(resolve_harness_root "" /tmp/nope)" "$HOME"
}

check_harness_ref_inner_load_pinned() {
  local root="$1"; local run="$2"
  local fx; fx="$(mktemp -d)"
  local sha; sha="$(_setup_inner_load_fixture "$fx")"
  _run_inner_load_probe "$run" "$fx" "$sha"
  assert "harness-ref inner load: stub log exists" is_file "$fx/stub.log"
  assert "harness-ref inner load: reads sha1 content" _grep "$fx/stub.log" "sha1-marker"
  assert_not "harness-ref inner load: not sha2 content" _grep "$fx/stub.log" "sha2-marker"
  rm -rf "$fx"
}

_setup_inner_load_fixture() {
  local fx="$1"; mkdir -p "$fx/repo/skills/foo"
  (cd "$fx/repo" && git init -q && git config user.email t@t && git config user.name t \
    && _commit_marker "skills/foo/SKILL.md" "sha1-marker" v1 \
    && git rev-parse HEAD > "$fx/sha1" \
    && _commit_marker "skills/foo/SKILL.md" "sha2-marker" v2) >&2
  cat "$fx/sha1"
}

_commit_marker() {
  printf '%s\n' "$2" > "$1"; git add "$1"; git commit -q -m "$3"
}

_run_inner_load_probe() {
  local run="$1"; local fx="$2"; local sha="$3"
  local stub="$fx/stub.sh"
  printf '#!/usr/bin/env bash\ncat "$HOME/.claude/skills/foo/SKILL.md" > "%s/stub.log" 2>&1\n' "$fx" > "$stub"
  chmod +x "$stub"
  CLAUDE_HARNESS_REPO="$fx/repo" EVAL_RUNS_DIR="$fx/runs" EVAL_INNER_STUB="$stub" \
    bash "$run/run-case.sh" --case-id per-project-instincts-bootstrap-pr19 \
      --run-id rload --harness-ref "$sha" --timeout 10 >/dev/null 2>&1
}

_grep() { grep -q "$2" "$1"; }

check_isolation_paths() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/isolation.sh"
  assert "shadow_home_path: under run-dir/home" _eq "$(shadow_home_path /tmp/eval-r1 c5)" "/tmp/eval-r1/home/c5"
  assert "inner_state_dir: under run-dir/inner" _eq "$(inner_state_dir /tmp/eval-r1 c5)" "/tmp/eval-r1/inner/c5"
}

check_isolation_env() {
  local run="$1"; local tmp; tmp="$(mktemp -d)"
  [ -f "$run/lib/isolation.sh" ] || { assert "isolation.sh exists" false; return; }
  # shellcheck disable=SC1091
  source "$run/lib/isolation.sh"
  export_isolation_env r42 c7 "$tmp/home"
  assert "isolation: CLAUDE_PIPELINE_TASK_ID" _eq "${CLAUDE_PIPELINE_TASK_ID:-}" "eval-r42-c7"
  assert "isolation: CLAUDE_PIPELINE_BYPASS=1" _eq "${CLAUDE_PIPELINE_BYPASS:-}" "1"
  assert "isolation: CLAUDE_DISABLE_AUTO_LEARN=1" _eq "${CLAUDE_DISABLE_AUTO_LEARN:-}" "1"
  assert "isolation: CLAUDE_PROJECT_HASH" _eq "${CLAUDE_PROJECT_HASH:-}" "eval-r42-c7"
  assert "isolation: EVAL_RUN_ID" _eq "${EVAL_RUN_ID:-}" "r42"
  assert "isolation: EVAL_CASE_ID" _eq "${EVAL_CASE_ID:-}" "c7"
  assert "isolation: HOME is shadow" _eq "${HOME:-}" "$tmp/home"
  rm -rf "$tmp"
}

_eq() { [ "$1" = "$2" ]; }

check_status_enum() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  assert "status.sh: passed is valid"        is_valid_status "passed"
  assert "status.sh: failed_diff is valid"   is_valid_status "failed_diff"
  assert "status.sh: failed_build is valid"  is_valid_status "failed_build"
  assert "status.sh: failed_timeout is valid" is_valid_status "failed_timeout"
  assert "status.sh: failed_infra is valid"  is_valid_status "failed_infra"
  assert "status.sh: dry_run_ok is valid"    is_valid_status "dry_run_ok"
  assert_not "status.sh: bogus is invalid"   is_valid_status "bogus"
}
