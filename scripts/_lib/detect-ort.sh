#!/usr/bin/env bash
# detect_ort — echoes absolute path to libonnxruntime, or empty if absent.
# Respects ORT_DYLIB_PATH override; otherwise probes OS-dispatched candidates.
# Tests override ORT_DYLIB_PATH or ORT_CANDIDATE_PATHS to stay hermetic.
# shellcheck source=detect-os.sh
source "$(dirname "${BASH_SOURCE[0]}")/detect-os.sh"

_ort_candidates_for_os() {
  case "$1" in
    macos) echo "/opt/homebrew/lib/libonnxruntime.dylib /usr/local/lib/libonnxruntime.dylib" ;;
    ubuntu|debian) echo "/usr/lib/x86_64-linux-gnu/libonnxruntime.so /usr/lib/libonnxruntime.so /usr/local/lib/libonnxruntime.so" ;;
    *) echo "" ;;
  esac
}

_ort_candidate_list() {
  [[ -n "${ORT_CANDIDATE_PATHS+x}" ]] && { echo "${ORT_CANDIDATE_PATHS}"; return; }
  _ort_candidates_for_os "$(detect_os)"
}

detect_ort() {
  [[ -n "${ORT_DYLIB_PATH:-}" && -f "${ORT_DYLIB_PATH}" ]] \
    && { echo "${ORT_DYLIB_PATH}"; return 0; }
  local c; for c in $(_ort_candidate_list); do
    [[ -f "$c" ]] && { echo "$c"; return 0; }
  done
  return 0
}
