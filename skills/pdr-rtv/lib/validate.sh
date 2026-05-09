#!/usr/bin/env bash
# validate.sh — pdr-rtv shape validators for filesystem-bound identifiers.
#
# Public functions:
#   _pdr_validate_task_id <value>
#   _pdr_validate_slug    <value>
#
# Both reject empty input, leading-dot, embedded `..`, and any character
# outside `[a-zA-Z0-9_.-]`. They are sourced by `dispatch.sh`, `distill.sh`
# and `tournament.sh` at parse-args time so a malicious task_id or slug
# cannot escape the pipeline-state directory via path traversal.

_pdr_shape_check() {
  # Args: <function-name-for-error> <value>
  local fn="$1" v="$2"
  if [ -z "$v" ]; then
    echo "${fn}: empty value rejected" >&2
    return 2
  fi
  case "$v" in (.*) echo "${fn}: leading dot rejected: $v" >&2; return 2 ;; esac
  case "$v" in (*..*) echo "${fn}: '..' rejected: $v" >&2; return 2 ;; esac
  if ! [[ "$v" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "${fn}: disallowed characters: $v" >&2
    return 2
  fi
}

_pdr_validate_task_id() { _pdr_shape_check _pdr_validate_task_id "$1"; }
_pdr_validate_slug()    { _pdr_shape_check _pdr_validate_slug    "$1"; }

export -f _pdr_validate_task_id _pdr_validate_slug _pdr_shape_check
