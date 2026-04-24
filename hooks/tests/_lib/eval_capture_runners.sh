#!/usr/bin/env bash
# Process runners for eval-capture tests. Time the hook; shell out to the worker.

_run_hook_unacked() {
  local hooks="$1" tmp="$2" rc start end elapsed
  start=$(date +%s%N 2>/dev/null || date +%s)
  (cd "$tmp" && unset CLAUDE_EVAL_CAPTURE_ACKED && \
    hook_stdin_pr_merge 42 | bash "$hooks/eval-capture-on-merge.sh" >/dev/null 2>&1); rc=$?
  end=$(date +%s%N 2>/dev/null || date +%s); elapsed=$(( (end - start) / 1000000 ))
  printf '%s %s' "$rc" "$elapsed"
}

_run_hook_acked() {
  local hooks="$1" tmp="$2" rc start end elapsed
  start=$(date +%s%N 2>/dev/null || date +%s)
  (cd "$tmp" && export CLAUDE_EVAL_CAPTURE_ACKED=1 CLAUDE_EVAL_CAPTURE_NOFORK=1 && \
    hook_stdin_pr_merge 42 | bash "$hooks/eval-capture-on-merge.sh" >/dev/null 2>&1); rc=$?
  end=$(date +%s%N 2>/dev/null || date +%s); elapsed=$(( (end - start) / 1000000 ))
  printf '%s %s' "$rc" "$elapsed"
}

_run_worker() {
  local hooks="$1" tmp="$2" fix="$3" pr="$4" fixture="$5"
  (cd "$tmp" && PATH="$tmp/bin:$PATH" \
    CLAUDE_EVAL_FIX_DIR="$fix" CLAUDE_EVAL_FIXTURE="$fixture" \
    bash "$hooks/_lib/eval-capture-worker.sh" "$pr" 2>/dev/null) || true
}
