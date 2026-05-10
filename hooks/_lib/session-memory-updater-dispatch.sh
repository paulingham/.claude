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
  codebase-map)
    # Slice D AC23/AC24: codebase-map.md is generator-owned (rebuilt on every
    # SessionStart by the codebase-map hook). Refusal is permanent
    # architecture — generated artifacts are generator-owned regardless of
    # soak state. Fires BEFORE the seed-on-miss block below so the template
    # is never copied for a misrouted spawn.
    printf '{"error":"generated_artifact_misroute","field":"targetSection","action":"spawn_refused"}\n' >&2
    exit 1 ;;
  build-test|patterns|fragility) ;;
  active-work)
    printf '{"error":"active_work_misroute","field":"targetSection","action":"spawn_refused"}\n' >&2
    exit 1 ;;
  *)
    # Unknown section — accept (test compatibility for any future section);
    # orchestrator catches this before spawn via documented contract.
    exit 0 ;;
esac

# Seed-on-miss: the updater is Read+Edit-only and cannot create the target
# file. If targetFile is absent, seed it from the canonical template at
# session-memory/config/templates/{targetSection}.md so the updater can Read +
# Edit on first run. Idempotent: if the file already exists, do nothing.
if [[ ! -e "$_target_file" ]]; then
  _config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  _template="$_config_dir/session-memory/config/templates/${_target_section}.md"
  if [[ -f "$_template" ]]; then
    mkdir -p "$(dirname "$_target_file")" 2>/dev/null || true
    if cp "$_template" "$_target_file" 2>/dev/null; then
      printf '{"info":"seeded_from_template","targetFile":"%s","template":"%s"}\n' \
        "$_target_file" "$_template" >&2
    else
      printf '{"error":"seed_failed","targetFile":"%s","template":"%s","action":"spawn_refused"}\n' \
        "$_target_file" "$_template" >&2
      exit 1
    fi
  else
    printf '{"error":"template_missing","template":"%s","action":"spawn_refused"}\n' \
      "$_template" >&2
    exit 1
  fi
fi

exit 0
