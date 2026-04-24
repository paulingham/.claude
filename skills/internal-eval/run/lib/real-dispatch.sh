#!/usr/bin/env bash
# Real `claude -p /pipeline` dispatcher. Preflight resolves the binary + task
# file; postcheck guards against single-turn short-circuit (inner asked a
# question and exited before the pipeline ran).

# _invoke_real <run_dir> <inner>
# rc 0: pipeline ran to completion (stdout has PIPELINE_COMPLETE).
# rc 1: short-circuit or pipeline build failure.
# rc 2: infra failure (missing bin / missing task.md).
_invoke_real() {
  local bin="${EVAL_CLAUDE_BIN:-claude}" task rc
  task="${EVAL_CASES_DIR:-$PWD/eval/cases}/$CASE_ID/task.md"
  _real_preflight "$bin" "$task" || return 2
  run_with_timeout "$TIMEOUT_SEC" "$bin" -p "/pipeline $(cat "$task")" >"$2/pipeline.stdout" 2>"$2/pipeline.stderr"; rc=$?
  _real_postcheck "$rc" "$2/pipeline.stdout"
}

_real_preflight() {
  command -v "$1" >/dev/null 2>&1 || { echo "[run-case] claude bin not found: $1" >&2; return 1; }
  [ -f "$2" ] || { echo "[run-case] missing task.md: $2" >&2; return 1; }
}

# _real_postcheck <rc> <stdout-path>
# Non-zero rc passes through. rc=0 requires PIPELINE_COMPLETE in stdout.
_real_postcheck() {
  [ "$1" -ne 0 ] && return "$1"
  grep -q "PIPELINE_COMPLETE" "$2" 2>/dev/null && return 0
  echo "[run-case] inner stdout lacks PIPELINE_COMPLETE marker — short-circuit" >&2
  return 1
}
