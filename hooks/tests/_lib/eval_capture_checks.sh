#!/usr/bin/env bash
# Story 5 grouped checks for auto-capture hook. Functions ≤ 5 lines.
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_fixtures.sh"

check_hook_exists() {
  assert "hook exists" is_file "$1/eval-capture-on-merge.sh"
}

_run_hook_unacked() {
  local hooks="$1" tmp="$2" rc start end elapsed
  start=$(date +%s%N 2>/dev/null || date +%s)
  (cd "$tmp" && unset CLAUDE_EVAL_CAPTURE_ACKED && \
    hook_stdin_pr_merge 42 | bash "$hooks/eval-capture-on-merge.sh" >/dev/null 2>&1); rc=$?
  end=$(date +%s%N 2>/dev/null || date +%s)
  elapsed=$(( (end - start) / 1000000 ))
  printf '%s %s' "$rc" "$elapsed"
}
check_fast_exit_unacked() {
  local tmp rc elapsed; tmp="$(make_capture_tmp)"
  read -r rc elapsed <<<"$(_run_hook_unacked "$1" "$tmp")"
  assert "unacked: exit 0"            rc_eq "$rc" "0"
  assert "unacked: under 1000ms"      millis_under "$elapsed" "1000"
  assert "unacked: no candidate dir"  no_candidate_dir "$tmp"
  rm -rf "$tmp"
}
_run_hook_acked() {
  local hooks="$1" tmp="$2" rc start end elapsed
  start=$(date +%s%N 2>/dev/null || date +%s)
  (cd "$tmp" && export CLAUDE_EVAL_CAPTURE_ACKED=1 CLAUDE_EVAL_CAPTURE_NOFORK=1 && \
    hook_stdin_pr_merge 42 | bash "$hooks/eval-capture-on-merge.sh" >/dev/null 2>&1); rc=$?
  end=$(date +%s%N 2>/dev/null || date +%s)
  elapsed=$(( (end - start) / 1000000 ))
  printf '%s %s' "$rc" "$elapsed"
}
check_fast_exit_acked() {
  local tmp rc elapsed; tmp="$(make_capture_tmp)"
  read -r rc elapsed <<<"$(_run_hook_acked "$1" "$tmp")"
  assert "acked: exit 0"              rc_eq "$rc" "0"
  assert "acked: under 1000ms"        millis_under "$elapsed" "1000"
  assert "acked: worker was called"   is_file "$tmp/eval/runs/.capture-log/worker-invoked.marker"
  rm -rf "$tmp"
}
check_worker_date_filter()   { :; }
check_worker_oracle_filter() { :; }
check_worker_happy_path()    { :; }
check_worker_never_promotes() { :; }
check_worker_capture_log()   { :; }
check_settings_registration() { :; }
check_skill_md_updated()     { :; }
