#!/usr/bin/env bash
# Test helpers for Story 7 run-suite.sh. Each check function performs a single
# focused assertion; keeps the test runner thin.

_eq() { [ "$1" = "$2" ]; }

check_suite_args_required() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r1
  assert "suite-args: RUN_ID populated" _eq "$RUN_ID" "r1"
}

check_suite_args_defaults() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r1
  assert "suite-args: default suite"         _eq "$SUITE" "default"
  assert "suite-args: default model"         _eq "$MODEL" "opus"
  assert "suite-args: default concurrency=4" _eq "$CONCURRENCY" "4"
  assert "suite-args: default harness empty" _eq "$HARNESS_REF" ""
  assert "suite-args: default resume=0"      _eq "$RESUME" "0"
}

check_suite_args_flags() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r2 --suite custom --model sonnet \
    --concurrency 8 --harness-ref deadbeef --resume
  assert "suite-args: --suite"        _eq "$SUITE" "custom"
  assert "suite-args: --model"        _eq "$MODEL" "sonnet"
  assert "suite-args: --concurrency"  _eq "$CONCURRENCY" "8"
  assert "suite-args: --harness-ref"  _eq "$HARNESS_REF" "deadbeef"
  assert "suite-args: --resume"       _eq "$RESUME" "1"
}

check_resume_detection() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-resume.sh"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/c1"; : > "$tmp/cases/c1/result.json"
  assert     "resume: c1 done → true"        case_already_done "$tmp" c1
  assert_not "resume: c2 not done → false"   case_already_done "$tmp" c2
  rm -rf "$tmp"
}

_make_cases() {
  local cases_root="$1"; shift
  for c in "$@"; do
    mkdir -p "$cases_root/$c"
    printf '# %s\n' "$c" > "$cases_root/$c/task.md"
  done
}

_pass_stub() {
  local dst="$1"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$dst"; chmod +x "$dst"
}

check_suite_end_to_end() {
  local run="$1"
  local tmp; tmp="$(mktemp -d)"
  _make_cases "$tmp/cases" a b c
  local stub="$tmp/pass.sh"; _pass_stub "$stub"
  EVAL_CASES_DIR="$tmp/cases" EVAL_RUNS_DIR="$tmp/runs" EVAL_INNER_STUB="$stub" \
    bash "$run/run-suite.sh" --run-id e2e --concurrency 2 >/dev/null
  assert "e2e: aggregate.json exists" is_file "$tmp/runs/e2e/aggregate.json"
  assert "e2e: suite.json exists"      is_file "$tmp/runs/e2e/suite.json"
  assert "e2e: all 3 result.jsons" \
    _eq "$(find "$tmp/runs/e2e/cases" -name result.json | wc -l | tr -d ' ')" "3"
  assert "e2e: passed=3" _eq "$(jq -r .passed "$tmp/runs/e2e/aggregate.json")" "3"
  rm -rf "$tmp"
}

check_suite_sigint() {
  local run="$1"
  local tmp; tmp="$(mktemp -d)"
  _make_cases "$tmp/cases" a b c d
  # Slow stub so we can signal mid-run. Use SIGTERM: background bash scripts
  # ignore SIGINT by default (POSIX job-control). Production CI also uses TERM.
  local stub="$tmp/slow.sh"
  printf '#!/usr/bin/env bash\nsleep 3\n' > "$stub"; chmod +x "$stub"
  EVAL_CASES_DIR="$tmp/cases" EVAL_RUNS_DIR="$tmp/runs" EVAL_INNER_STUB="$stub" \
    bash "$run/run-suite.sh" --run-id rsig --concurrency 2 & local pid=$!
  sleep 0.8; kill -TERM "$pid" 2>/dev/null; wait "$pid" 2>/dev/null || true
  assert "signal: suite.json status = interrupted" \
    _eq "$(jq -r .status "$tmp/runs/rsig/suite.json" 2>/dev/null)" "interrupted"
  assert "signal: aggregate.json written on interrupt" \
    is_file "$tmp/runs/rsig/aggregate.json"
  rm -rf "$tmp"
}

check_suite_harness_shared_once() {
  local run="$1"
  local tmp; tmp="$(mktemp -d)"
  _make_cases "$tmp/cases" a b c
  local stub="$tmp/pass.sh"; _pass_stub "$stub"
  # Set up a tiny fixture repo so --harness-ref has something real to check out.
  mkdir -p "$tmp/hrepo"
  (cd "$tmp/hrepo" && git init -q && git config user.email t@t && git config user.name t \
    && touch marker && git add marker && git commit -q -m v1) >/dev/null
  local sha; sha="$(cd "$tmp/hrepo" && git rev-parse HEAD)"
  EVAL_CASES_DIR="$tmp/cases" EVAL_RUNS_DIR="$tmp/runs" EVAL_INNER_STUB="$stub" \
    CLAUDE_HARNESS_REPO="$tmp/hrepo" \
    bash "$run/run-suite.sh" --run-id rhw --concurrency 2 --harness-ref "$sha" >/dev/null
  assert "harness-shared: single harness worktree under run-dir" \
    is_dir "$tmp/runs/rhw/harness-wt"
  # The worktree appears exactly once; not per case.
  local wt_count; wt_count="$(find "$tmp/runs/rhw" -name harness-wt -type d | wc -l | tr -d ' ')"
  assert "harness-shared: exactly one harness-wt directory" _eq "$wt_count" "1"
  rm -rf "$tmp"
}

check_suite_enumeration() {
  local run="$1"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/_example" "$tmp/cases/.candidates" \
           "$tmp/cases/real-one" "$tmp/cases/real-two"
  # shellcheck disable=SC1091
  source "$run/lib/suite-enumerate.sh"
  local cases; cases="$(enumerate_cases default "$tmp/cases" | LC_ALL=C sort | tr '\n' ' ')"
  assert "enumerate: default suite excludes _example and .candidates" \
    _eq "$cases" "real-one real-two "
  rm -rf "$tmp"
}

check_suite_resume_skips() {
  local run="$1"
  local tmp; tmp="$(mktemp -d)"
  _make_cases "$tmp/cases" a b c
  local stub="$tmp/pass.sh"; _pass_stub "$stub"
  # Pre-seed case "a" as already done with a sentinel content.
  mkdir -p "$tmp/runs/rsum/cases/a"
  echo '{"status":"preserved","case_id":"a"}' > "$tmp/runs/rsum/cases/a/result.json"
  EVAL_CASES_DIR="$tmp/cases" EVAL_RUNS_DIR="$tmp/runs" EVAL_INNER_STUB="$stub" \
    bash "$run/run-suite.sh" --run-id rsum --concurrency 2 --resume >/dev/null
  assert "resume: case a result.json preserved (not rewritten)" \
    _eq "$(jq -r .status "$tmp/runs/rsum/cases/a/result.json")" "preserved"
  assert "resume: case b rewritten"  is_file "$tmp/runs/rsum/cases/b/result.json"
  rm -rf "$tmp"
}

check_pool_runs_all() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-pool.sh"
  local tmp; tmp="$(mktemp -d)"
  _pool_launcher() { local c="$1"; : > "$tmp/done-$c"; }
  run_pool 2 _pool_launcher a b c d e
  local done_count; done_count="$(ls "$tmp"/done-* 2>/dev/null | wc -l | tr -d ' ')"
  assert "pool: all 5 cases ran" _eq "$done_count" "5"
  rm -rf "$tmp"
}

check_pool_respects_concurrency() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-pool.sh"
  local tmp; tmp="$(mktemp -d)"
  # Launcher writes pid-start-stop markers; assert no 3 overlap (concurrency=2).
  _concurrent_launcher() { _mark_start_stop "$tmp" "$1"; }
  run_pool 2 _concurrent_launcher a b c d
  local max_overlap; max_overlap="$(_compute_max_overlap "$tmp")"
  assert "pool: max parallel ≤ concurrency (2)" test "$max_overlap" -le 2
  rm -rf "$tmp"
}

_mark_start_stop() {
  local dir="$1"; local c="$2"
  date +%s.%N > "$dir/start-$c"; sleep 0.3; date +%s.%N > "$dir/stop-$c"
}

_compute_max_overlap() {
  local dir="$1"
  # Build timeline: each start event +1, each stop -1, running max.
  { for f in "$dir"/start-*; do printf "%s +1\n" "$(cat "$f")"; done
    for f in "$dir"/stop-*;  do printf "%s -1\n" "$(cat "$f")"; done; } \
    | sort -n | awk 'BEGIN{m=0;c=0}{c+=$2; if(c>m)m=c}END{print m}'
}

check_shared_harness_live() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-harness.sh"
  local root; root="$(setup_shared_harness "" /tmp/suite-wt-nope)"
  assert "shared-harness: empty SHA → \$HOME" _eq "$root" "$HOME"
}

check_shared_harness_pinned() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-harness.sh"
  local fx; fx="$(mktemp -d)"; mkdir -p "$fx/repo"
  local sha; sha="$(_suite_setup_fixture "$fx")"
  local root; root="$(CLAUDE_HARNESS_REPO="$fx/repo" setup_shared_harness "$sha" "$fx/wt")"
  assert "shared-harness: pinned returns wt path" _eq "$root" "$fx/wt"
  assert "shared-harness: worktree directory exists" is_dir "$fx/wt"
  # Call again with same SHA: should NOT re-create (idempotent).
  local root2; root2="$(CLAUDE_HARNESS_REPO="$fx/repo" setup_shared_harness "$sha" "$fx/wt")"
  assert "shared-harness: second call same path (reuse)" _eq "$root2" "$fx/wt"
  rm -rf "$fx"
}

_suite_setup_fixture() {
  local fx="$1"
  (cd "$fx/repo" && git init -q && git config user.email t@t && git config user.name t \
    && touch x && git add x && git commit -q -m v1) >&2
  (cd "$fx/repo" && git rev-parse HEAD)
}

_write_stub_result() {
  local path="$1"; local status="$2"; local cid="$3"
  mkdir -p "$(dirname "$path")"
  jq -n --arg s "$status" --arg c "$cid" \
    '{case_id:$c,run_id:"r",status:$s,duration_sec:1,cost_usd:0.25}' > "$path"
}

check_aggregate_counts() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" passed a
  _write_stub_result "$tmp/cases/b/result.json" passed b
  _write_stub_result "$tmp/cases/c/result.json" failed_diff c
  _write_stub_result "$tmp/cases/d/result.json" failed_infra d
  aggregate_run "$tmp" r1 default opus deadbeef
  local agg="$tmp/aggregate.json"
  assert "aggregate: total=4"         _eq "$(jq -r .total_cases "$agg")" "4"
  assert "aggregate: passed=2"        _eq "$(jq -r .passed "$agg")" "2"
  assert "aggregate: failed_diff=1"   _eq "$(jq -r .failed_diff "$agg")" "1"
  assert "aggregate: failed_infra=1"  _eq "$(jq -r .failed_infra "$agg")" "1"
  rm -rf "$tmp"
}

check_aggregate_pass_rate() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" passed a
  _write_stub_result "$tmp/cases/b/result.json" failed_diff b
  _write_stub_result "$tmp/cases/c/result.json" failed_infra c
  aggregate_run "$tmp" r1 default opus live
  assert "aggregate: pass_rate excludes failed_infra" \
    _eq "$(jq -r .pass_rate "$tmp/aggregate.json")" "0.5"
  rm -rf "$tmp"
}

check_aggregate_empty_denominator() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" failed_infra a
  aggregate_run "$tmp" r1 default opus live
  assert "aggregate: all infra → pass_rate 0" \
    _eq "$(jq -r .pass_rate "$tmp/aggregate.json")" "0"
  rm -rf "$tmp"
}

check_resume_filter() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-resume.sh"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/done"; : > "$tmp/cases/done/result.json"
  local pending
  pending="$(filter_pending_cases 1 "$tmp" done todo1 todo2 | tr '\n' ' ')"
  assert "resume: filters to pending only" _eq "$pending" "todo1 todo2 "
  pending="$(filter_pending_cases 0 "$tmp" done todo1 todo2 | tr '\n' ' ')"
  assert "resume: no-resume returns all"   _eq "$pending" "done todo1 todo2 "
  rm -rf "$tmp"
}
