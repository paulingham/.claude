#!/usr/bin/env bash
# Story 9 — emits the "## Eval Baseline" markdown section for a PR body.
# Reads eval/baselines/latest-{model}.md (model defaults to opus-4-7).
# If no baseline exists, emits a graceful stub. Output to stdout.
set -eu
SCORE_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/stamp-format.sh
source "$SCORE_DIR/lib/stamp-format.sh"

MODEL="opus-4-7"

main() {
  _parse_args "$@"
  local dir="${EVAL_BASELINES_DIR:-$PWD/eval/baselines}"
  local link="$dir/latest-$MODEL.md"
  [ -L "$link" ] || [ -f "$link" ] || { emit_stamp_stub; exit 0; }
  _emit_from "$link" "$dir"
}

_parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --model) MODEL="$2"; shift 2 ;;
      *) echo "[stamp-pr-body] unknown arg: $1" >&2; exit 2 ;;
    esac
  done
}

_emit_from() {
  local link="$1"; local dir="$2"
  local target; target="$(readlink "$link" 2>/dev/null || basename "$link")"
  local rel="eval/baselines/$target"
  emit_stamp_body "$link" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rel"
}

main "$@"
