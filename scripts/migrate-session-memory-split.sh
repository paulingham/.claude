#!/usr/bin/env bash
# AC2/AC3/AC13/AC14 — split legacy notes.md into 5 sub-files.
# Idempotent (skip if already migrated). Non-destructive (rename, not delete).
# Refuses to operate on symlinks pointing outside the config root. Supports
# --dry-run.
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
STORE_ROOT="$CONFIG_DIR/session-memory"
[[ -d "$STORE_ROOT" ]] || { echo "OK (no session-memory)"; exit 0; }

CANONICAL=(codebase-map build-test patterns fragility active-work)

_resolved_root="$(cd "$STORE_ROOT" && pwd -P)"

_within_root() {
  # Refuse if the resolved candidate path leaves $STORE_ROOT.
  local target="$1" resolved
  resolved=$(cd "$target" 2>/dev/null && pwd -P) || return 1
  case "$resolved/" in "$_resolved_root"/*) return 0 ;; esac
  return 1
}

_already_migrated() {
  local proj="$1" sub
  for sub in "${CANONICAL[@]}"; do
    [[ -f "$proj/$sub.md" ]] || return 1
  done
  return 0
}

_extract_section() {
  local notes="$1" header="$2"
  awk -v h="$header" '
    BEGIN { found=0 }
    /^# / { if (found) exit; if ($0 == h) { found=1; next } }
    found { print }
  ' "$notes"
}

_write_subfile() {
  local proj="$1" sub="$2" header="$3" desc="$4" body="$5"
  local target="$proj/$sub.md"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'would create %s\n' "$target"
    return 0
  fi
  {
    printf '# %s\n' "$header"
    printf '_%s_\n' "$desc"
    printf '%s' "$body"
  } > "$target"
}

_archive_existing_legacy() {
  local proj="$1"
  local existing="$proj/notes.md.legacy"
  [[ -f "$existing" ]] || return 0
  local ts; ts=$(date +%s)
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'would archive %s -> %s.%s\n' "$existing" "$existing" "$ts"
    return 0
  fi
  mv "$existing" "$existing.$ts"
}

_split_notes() {
  local proj="$1"
  local notes="$proj/notes.md"
  local cmap btest patt frag awork
  cmap=$(_extract_section "$notes" "# Codebase Map")
  btest=$(_extract_section "$notes" "# Build & Test")
  frag=$(_extract_section "$notes" "# Critical Paths")
  awork=$(_extract_section "$notes" "# Active Work")
  # patterns merges three legacy headers.
  local p1 p2 p3
  p1=$(_extract_section "$notes" "# Patterns & Conventions")
  p2=$(_extract_section "$notes" "# Session Discoveries")
  p3=$(_extract_section "$notes" "# Agent Effectiveness")
  patt=$(printf '%s%s%s' "$p1" "$p2" "$p3")
  _write_subfile "$proj" codebase-map "Codebase Map" \
    "Key directories and files. What they contain. How they connect." "$cmap"
  _write_subfile "$proj" build-test "Build & Test" \
    "Commands that work. Env setup. Test runner quirks." "$btest"
  _write_subfile "$proj" patterns "Patterns & Conventions" \
    "Patterns, idioms, session discoveries, agent effectiveness." "$patt"
  _write_subfile "$proj" fragility "Critical Paths" \
    "Fragile files, timing sensitivities, areas needing care." "$frag"
  _write_subfile "$proj" active-work "Active Work" \
    "Current pipeline phase, task, branch. Orchestrator-only — never injected." "$awork"
}

_rename_legacy() {
  local proj="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'would rename %s/notes.md -> %s/notes.md.legacy\n' "$proj" "$proj"
    return 0
  fi
  mv "$proj/notes.md" "$proj/notes.md.legacy"
}

_handle_project() {
  local proj="$1"
  # Symlink discipline: refuse if resolved path escapes STORE_ROOT.
  _within_root "$proj" || {
    printf 'REFUSING: %s resolves outside %s\n' "$proj" "$_resolved_root" >&2
    return 0
  }
  if _already_migrated "$proj"; then
    [[ -f "$proj/notes.md" ]] && _rename_legacy "$proj"
    return 0
  fi
  [[ -f "$proj/notes.md" ]] || return 0
  _archive_existing_legacy "$proj"
  _split_notes "$proj"
  _rename_legacy "$proj"
}

shopt -s nullglob
for _entry in "$STORE_ROOT"/*/; do
  [[ "$_entry" == *"/config/" ]] && continue
  _handle_project "${_entry%/}"
done
shopt -u nullglob

[[ "$DRY_RUN" -eq 1 ]] && echo "DRY-RUN: no files modified" || echo "OK"
