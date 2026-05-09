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

# Source the shared validator (path-traversal defense, F1).
_pdr_distill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "${_pdr_distill_dir}/validate.sh"
unset _pdr_distill_dir

_pdr_distill_validate_args() {
  local fn_name="$1"; shift
  if [ "$#" -ne 4 ]; then
    echo "${fn_name}: usage: ${fn_name} <worktree> <state_root> <task_id> <slug>" >&2
    return 2
  fi
  for arg in "$@"; do
    [ -n "$arg" ] || { echo "${fn_name}: empty argument" >&2; return 2; }
  done
  # Position 3 = task_id, position 4 = slug (worktree + state_root are paths).
  _pdr_validate_task_id "$3" || return $?
  _pdr_validate_slug "$4"    || return $?
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

# F4 secret redaction — replace secret-shaped substrings with
# `[REDACTED:<class>]` and emit one forensic JSONL record per pattern class
# matched. Does NOT abort distillation on detection; redaction with
# visibility is the right balance (false-positive risk on aborts is high).
_pdr_distill_redact_secrets() {
  # Args: <task_id> <text>; emits redacted text on stdout, JSONL records as
  # side-effect via _pdr_emit_redaction_record.
  local task_id="$1" text="$2"
  local classes
  classes="$(_pdr_distill_classes_matched "$text")"
  text="$(printf '%s' "$text" | _pdr_apply_redactions)"
  local cls
  for cls in $classes; do
    _pdr_emit_redaction_record "$task_id" "$cls"
  done
  printf '%s' "$text"
}

_pdr_distill_classes_matched() {
  # Args: <text>. Emits matched class names (one per line, deduped).
  local text="$1"
  {
    printf '%s' "$text" | grep -Eq 'AKIA[0-9A-Z]{16}'        && echo aws-key
    printf '%s' "$text" | grep -Eq 'gh[pousr]_[A-Za-z0-9]{36,}' && echo github-token
    printf '%s' "$text" | grep -Eq '[A-Za-z0-9+/=]{40,}'      && echo high-entropy
    printf '%s' "$text" | grep -Eq '^[A-Z_]+=[^[:space:]]{20,}$' && echo env-style
  } | awk '!seen[$0]++'
}

_pdr_apply_redactions() {
  # Reads stdin, applies regex-based redactions, writes to stdout.
  # Order: env-style (line-anchored) FIRST so its value isn't pre-mangled by
  # high-entropy. AWS and GitHub before high-entropy so the more specific
  # class label is used; otherwise high-entropy would catch first.
  sed -E \
    -e 's/^[A-Z_]+=[^[:space:]]{20,}$/[REDACTED:env-style]/g' \
    -e 's/AKIA[0-9A-Z]{16}/[REDACTED:aws-key]/g' \
    -e 's/gh[pousr]_[A-Za-z0-9]{36,}/[REDACTED:github-token]/g' \
    -e 's/[A-Za-z0-9+\/=]{40,}/[REDACTED:high-entropy]/g'
}

_pdr_emit_redaction_record() {
  # Args: <task_id> <pattern_class>. Appends one JSON line to
  # metrics/{session}/pdr-secret-redactions.jsonl.
  local task_id="$1" pattern_class="$2"
  local session="${CLAUDE_SESSION_ID:-local-$$}"
  session="${session//[^A-Za-z0-9_-]/_}"
  [[ -z "$session" || "$session" =~ ^_+$ ]] && session="local-$$"
  local dir="${HOME}/.claude/metrics/${session}"
  mkdir -p "$dir" 2>/dev/null || return 0
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"timestamp": "%s", "source": "pdr-secret-redacted", "task_id": "%s", "pattern_class": "%s"}\n' \
    "$ts" "$task_id" "$pattern_class" \
    >> "${dir}/pdr-secret-redactions.jsonl" 2>/dev/null || true
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

  hypotheses="$(_pdr_distill_redact_secrets "$task_id" "$hypotheses")"
  progress="$(_pdr_distill_redact_secrets   "$task_id" "$progress")"
  failures="$(_pdr_distill_redact_secrets   "$task_id" "$failures")"

  out_file="${state_root}/${task_id}/pdr-rtv/rollouts/${slug}/summary.md"
  _pdr_distill_write_summary "$out_file" "$hypotheses" "$progress" "$failures"
}

export -f distill_rollout \
          _pdr_distill_validate_args \
          _pdr_distill_read_commit_block \
          _pdr_distill_extract_field \
          _pdr_distill_redact_secrets \
          _pdr_distill_classes_matched \
          _pdr_apply_redactions \
          _pdr_emit_redaction_record \
          _pdr_distill_write_summary
