#!/usr/bin/env bash
# EVAL_INNER_STUB for the Story 11 validation sequence. Reads a manifest at
# $VALIDATE_STUB_MANIFEST (JSON: {case-id: "pass"|"fail"}) and exits with rc
# reflecting the scripted status. Unlisted cases default to pass. Args are
# (run_dir, inner) per run-case.sh's _invoke_stub contract.
set -u

_case_id_from_inner() { basename "$1"; }

_lookup_status() {
  local manifest="$1"; local case_id="$2"
  jq -r --arg c "$case_id" '.[$c] // "pass"' "$manifest" 2>/dev/null || echo pass
}

_rc_for_status() {
  case "$1" in pass) return 0 ;; fail) return 1 ;; *) return 0 ;; esac
}

main() {
  local inner="${2:-}"
  [ -n "${VALIDATE_STUB_MANIFEST:-}" ] || { echo "[stub-manifest] VALIDATE_STUB_MANIFEST unset" >&2; exit 2; }
  local case_id; case_id="$(_case_id_from_inner "$inner")"
  local status; status="$(_lookup_status "$VALIDATE_STUB_MANIFEST" "$case_id")"
  _rc_for_status "$status"
}

main "$@"
