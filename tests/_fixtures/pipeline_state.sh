#!/usr/bin/env bash
# Slice E.5 — pipeline-state fixture helper for shell tests (bash 3.2).
#
# Usage:
#   _psf_make_fixture --task-id=ID [--layout=new|legacy] [--workstream=WS] \
#                     [--phases='pipeline build'] [--verdict=in_progress] \
#                     STATE_DIR
#
# Echoes the path to `{task}-pipeline.md` (legacy) or `{task}/pipeline.md`
# (new). Default layout is "new"; default phases is "pipeline".

# shellcheck disable=SC2155
_PSF_TASK="" _PSF_LAYOUT=new _PSF_WS="" _PSF_PHASES=pipeline
_PSF_VERDICT=in_progress _PSF_DIR=""

_psf_phase_path() {
  local state_dir="$1" task="$2" phase="$3" layout="$4" ws="$5"
  local root="$state_dir"
  [ -n "$ws" ] && root="$state_dir/workstreams/$ws"
  [ "$layout" = "new" ] && { printf '%s/%s/%s.md\n' "$root" "$task" "$phase"; return; }
  printf '%s/%s-%s.md\n' "$root" "$task" "$phase"
}

_psf_write_state() {
  local path="$1" task="$2" phase="$3" verdict="$4"
  mkdir -p "$(dirname "$path")"
  printf -- '---\ntask_id: %s\nphase: %s\nverdict: %s\n---\n' \
    "$task" "$phase" "$verdict" > "$path"
}

_psf_validate() {
  [ -z "$1" ] && { echo "_psf_make_fixture: --task-id required" >&2; return 1; }
  [ -z "$2" ] && { echo "_psf_make_fixture: STATE_DIR required" >&2; return 1; }
  case "$3" in new|legacy) return 0 ;; esac
  echo "_psf_make_fixture: bad layout: $3" >&2; return 1
}

_psf_parse_one() {
  case "$1" in
    --task-id=*)    _PSF_TASK="${1#--task-id=}" ;;
    --layout=*)     _PSF_LAYOUT="${1#--layout=}" ;;
    --workstream=*) _PSF_WS="${1#--workstream=}" ;;
    --phases=*)     _PSF_PHASES="${1#--phases=}" ;;
    --verdict=*)    _PSF_VERDICT="${1#--verdict=}" ;;
    *)              _PSF_DIR="$1" ;;
  esac
}

_psf_emit() {
  local state_dir="$1" task="$2" layout="$3" ws="$4" phases="$5" verdict="$6"
  local pipeline_path="" path phase
  for phase in $phases; do
    path="$(_psf_phase_path "$state_dir" "$task" "$phase" "$layout" "$ws")"
    _psf_write_state "$path" "$task" "$phase" "$verdict"
    [ "$phase" = "pipeline" ] && pipeline_path="$path"
  done
  [ -z "$pipeline_path" ] && pipeline_path="$(_psf_phase_path "$state_dir" "$task" pipeline "$layout" "$ws")"
  printf '%s\n' "$pipeline_path"
}

_psf_make_fixture() {
  _PSF_TASK="" _PSF_LAYOUT=new _PSF_WS="" _PSF_PHASES=pipeline
  _PSF_VERDICT=in_progress _PSF_DIR=""
  while [ "$#" -gt 0 ]; do _psf_parse_one "$1"; shift; done
  _psf_validate "$_PSF_TASK" "$_PSF_DIR" "$_PSF_LAYOUT" || return 1
  _psf_emit "$_PSF_DIR" "$_PSF_TASK" "$_PSF_LAYOUT" "$_PSF_WS" "$_PSF_PHASES" "$_PSF_VERDICT"
}
