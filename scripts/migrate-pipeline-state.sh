#!/usr/bin/env bash
# Slice F (AC #7) — clean pre-existing terminal pipelines from
# pipeline-state/. Refuses to delete unless verdict is in the terminal
# allowlist; refuses on partial-cleanup state (phase files without a
# {prefix}-pipeline.md). Idempotent.
set -euo pipefail

PIPELINE_DIR="${PIPELINE_STATE_DIR:-${HOME}/.claude/pipeline-state}"
TERMINAL_PREFIXES=("thinking-defaults-xhigh" "wave4-S")
TERMINAL_VERDICTS_RE='^verdict: (completed|PR_CREATED|MERGED|FAILED|REJECTED)$'

_mps_matches() {
  local prefix="$1" scratch="$PIPELINE_DIR/${prefix}-scratchpad"
  shopt -s nullglob
  local m=("$PIPELINE_DIR/${prefix}-"*.md "$PIPELINE_DIR/${prefix}-"*.token)
  shopt -u nullglob
  [ -d "$scratch" ] && m+=("$scratch")
  printf '%d\n' "${#m[@]}"
}

_mps_guard() {
  local prefix="$1" pipe="$PIPELINE_DIR/${prefix}-pipeline.md"
  [ ! -f "$pipe" ] && { printf 'REFUSING: %s has phase files but no %s\n' "$prefix" "$pipe" >&2; exit 2; }
  grep -Eq "$TERMINAL_VERDICTS_RE" "$pipe" \
    || { printf 'REFUSING: %s is not in a terminal verdict\n' "$pipe" >&2; exit 2; }
}

_mps_purge() {
  local prefix="$1"
  rm -f "$PIPELINE_DIR/${prefix}-"*.md "$PIPELINE_DIR/${prefix}-"*.token
  rm -rf "$PIPELINE_DIR/${prefix}-scratchpad"
}

_mps_handle() {
  local prefix="$1"
  [ "$(_mps_matches "$prefix")" -eq 0 ] && { printf 'SKIP: %s has no matching files\n' "$prefix"; return; }
  _mps_guard "$prefix"
  _mps_purge "$prefix"
}

for _prefix in "${TERMINAL_PREFIXES[@]}"; do _mps_handle "$_prefix"; done
echo "OK"
