#!/usr/bin/env bash
# Story 5 hook-level + documentation checks. Worker-level checks live in sibling file.
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_helpers.sh"
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_worker_checks.sh"

check_hook_exists() { assert "hook exists" is_file "$1/eval-capture-on-merge.sh"; }

check_fast_exit_unacked() {
  local tmp rc elapsed; tmp="$(make_capture_tmp)"
  read -r rc elapsed <<<"$(_run_hook_unacked "$1" "$tmp")"
  assert "unacked: exit 0"           rc_eq "$rc" "0"
  assert "unacked: under 1000ms"     millis_under "$elapsed" "1000"
  assert "unacked: no candidate dir" no_candidate_dir "$tmp"
  rm -rf "$tmp"
}

check_fast_exit_acked() {
  local tmp rc elapsed; tmp="$(make_capture_tmp)"
  read -r rc elapsed <<<"$(_run_hook_acked "$1" "$tmp")"
  assert "acked: exit 0"            rc_eq "$rc" "0"
  assert "acked: under 1000ms"      millis_under "$elapsed" "1000"
  assert "acked: worker was called" is_file "$tmp/eval/runs/.capture-log/worker-invoked.marker"
  rm -rf "$tmp"
}

check_settings_registration() {
  assert "settings.json registers eval-capture hook" \
    grep_file "$1/settings.json" "eval-capture-on-merge.sh"
}

check_skill_md_updated() {
  local f="$1/skills/internal-eval/capture/SKILL.md"
  assert "SKILL.md: auto-capture section"      grep_file "$f" "Auto-capture"
  assert "SKILL.md: hook file named"           grep_file "$f" "eval-capture-on-merge.sh"
  assert "SKILL.md: candidates dir documented" grep_file "$f" ".candidates"
}
