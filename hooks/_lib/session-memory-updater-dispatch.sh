#!/usr/bin/env bash
# AC8 — guard helper: refuse to dispatch a session-memory-updater spawn
# when targetFile or targetSection is empty/blank/missing. Exit non-zero
# with a structured error written to stderr.
#
# Usage: session-memory-updater-dispatch.sh <targetFile> <targetSection>
# Exit 0  → both fields present and non-blank; orchestrator may proceed.
# Exit 1  → at least one field missing; do not spawn.
set -u

_target_file="${1-}"
_target_section="${2-}"

_blank() {
  case "${1//[[:space:]]/}" in "") return 0 ;; *) return 1 ;; esac
}

if _blank "$_target_file"; then
  printf '{"error":"missing_targetFile","field":"targetFile","action":"spawn_refused"}\n' >&2
  exit 1
fi

if _blank "$_target_section"; then
  printf '{"error":"missing_targetSection","field":"targetSection","action":"spawn_refused"}\n' >&2
  exit 1
fi

case "$_target_section" in
  codebase-map|build-test|patterns|fragility) exit 0 ;;
  active-work)
    printf '{"error":"active_work_misroute","field":"targetSection","action":"spawn_refused"}\n' >&2
    exit 1 ;;
  *)
    # Unknown section — accept (test compatibility for any future section);
    # orchestrator catches this before spawn via documented contract.
    exit 0 ;;
esac
