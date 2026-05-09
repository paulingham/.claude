#!/usr/bin/env bash
# distill.sh — pdr-rtv rollout distillation helper.
#
# Builds a compact `summary.md` from a build engineer's worktree, capturing
# the three sections required by the PDR-RTV paper (arXiv:2604.16529):
# Hypotheses Tried, Progress Made, Failure Modes.
#
# The summary persists OUTSIDE the worktree at
# `pipeline-state/{task-id}/pdr-rtv/rollouts/{slug}/summary.md` so the
# worktree can be reaped (per AC3-bis) before the next iteration spawns.
#
# Inputs (positional):
#   $1 = worktree path
#   $2 = state root (typically pipeline-state/, may be overridden in tests)
#   $3 = task id
#   $4 = slug (rollout identifier)
#
# Reads (in priority order):
#   <worktree>/COMMIT_MSG  — fenced [SUMMARY]...[/SUMMARY] block from the
#                            build engineer's commit message
#   git log -n 1            — same fenced block from the worktree HEAD commit
#
# Writes:
#   <state_root>/<task_id>/pdr-rtv/rollouts/<slug>/summary.md
#
# Exit 0 on success, non-zero on bad arguments.

_pdr_distill_validate_args() {
  local fn_name="$1"; shift
  if [ "$#" -ne 4 ]; then
    echo "${fn_name}: usage: ${fn_name} <worktree> <state_root> <task_id> <slug>" >&2
    return 2
  fi
  for arg in "$@"; do
    [ -n "$arg" ] || { echo "${fn_name}: empty argument" >&2; return 2; }
  done
}

_pdr_distill_read_commit_block() {
  local worktree="$1"
  if [ -f "$worktree/COMMIT_MSG" ]; then
    awk '/^\[SUMMARY\]/{flag=1; next} /^\[\/SUMMARY\]/{flag=0} flag' \
      "$worktree/COMMIT_MSG"
    return 0
  fi
  if git -C "$worktree" log -1 --pretty=%B 2>/dev/null \
       | awk '/^\[SUMMARY\]/{flag=1; next} /^\[\/SUMMARY\]/{flag=0} flag'; then
    return 0
  fi
  return 0
}

_pdr_distill_extract_field() {
  local block="$1" key="$2"
  echo "$block" | awk -v k="$key" '
    BEGIN { IGNORECASE=1; pat="^"k":[[:space:]]*" }
    $0 ~ pat { sub(pat, ""); print; exit }
  '
}

_pdr_distill_write_summary() {
  local out_file="$1" hypotheses="$2" progress="$3" failures="$4"
  mkdir -p "$(dirname "$out_file")"
  {
    echo "## Hypotheses Tried"
    echo "${hypotheses:-(none recorded)}"
    echo ""
    echo "## Progress Made"
    echo "${progress:-(none recorded)}"
    echo ""
    echo "## Failure Modes"
    echo "${failures:-(none recorded)}"
  } > "$out_file"
}

distill_rollout() {
  _pdr_distill_validate_args distill_rollout "$@" || return $?
  local worktree="$1" state_root="$2" task_id="$3" slug="$4"
  local block hypotheses progress failures out_file

  block="$(_pdr_distill_read_commit_block "$worktree")"
  hypotheses="$(_pdr_distill_extract_field "$block" "HYPOTHESES")"
  progress="$(_pdr_distill_extract_field "$block" "PROGRESS")"
  failures="$(_pdr_distill_extract_field "$block" "FAILURES")"

  out_file="${state_root}/${task_id}/pdr-rtv/rollouts/${slug}/summary.md"
  _pdr_distill_write_summary "$out_file" "$hypotheses" "$progress" "$failures"
}

export -f distill_rollout \
          _pdr_distill_validate_args \
          _pdr_distill_read_commit_block \
          _pdr_distill_extract_field \
          _pdr_distill_write_summary
