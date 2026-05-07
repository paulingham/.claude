#!/usr/bin/env bash
# Sync helpers — round-trip per sub-file (post-C3 split).
# Each canonical sub-file is stored under subkey == basename.
# Legacy 'notes' single-file path still tolerated for the soak window.

_SYNC_CANONICAL_SUBFILES=(codebase-map build-test patterns fragility active-work)

_sync_template_path() {
  # Legacy single-file template (used by _sync_in_legacy_file only). The
  # canonical template.md is now the index doc — the legacy seed lives at
  # template-legacy.md so legacy file-path callers still get all 7 sections.
  local legacy="$_SESSION_STORE_ROOT/session-memory/config/template-legacy.md"
  [[ -f "$legacy" ]] && { printf '%s\n' "$legacy"; return; }
  printf '%s\n' "$_SESSION_STORE_ROOT/session-memory/config/template.md"
}

_sync_subfile_template() {
  printf '%s/session-memory/config/templates/%s.md\n' "$_SESSION_STORE_ROOT" "$1"
}

_sync_stamp_subfile() {
  local target="$1" sub="$2" tmpl; tmpl=$(_sync_subfile_template "$sub")
  [[ -f "$tmpl" ]] || return 0
  (umask 077 && mkdir -p "$(dirname "$target")") 2>/dev/null
  (umask 077 && cp "$tmpl" "$target")
}

_sync_in_one() {
  local hash="$1" sub="$2" target="$3" blob
  if blob=$(session_store_get "$hash" "$sub" 2>/dev/null); then
    (umask 077 && printf '%s' "$blob" > "$target"); return 0
  fi
  [[ -f "$target" ]] && return 0
  _sync_stamp_subfile "$target" "$sub"
}

_sync_out_one() {
  local hash="$1" sub="$2" target="$3"
  [[ -f "$target" ]] || return 0
  session_store_put "$hash" "$sub" "$target" && return 0
  _sync_out_failure_log "$hash" "$target"
}

session_memory_sync_in() {
  local hash="$1" path="$2" backend sub
  backend=$(_resolve_backend)
  [[ "$backend" = "local" ]] && return 0
  [[ -d "$path" ]] || { _sync_in_legacy_file "$hash" "$path"; return; }
  for sub in "${_SYNC_CANONICAL_SUBFILES[@]}"; do
    _sync_in_one "$hash" "$sub" "$path/$sub.md"
  done
}

session_memory_sync_out() {
  local hash="$1" path="$2" backend sub
  backend=$(_resolve_backend)
  [[ "$backend" = "local" ]] && return 0
  [[ -d "$path" ]] || { _sync_out_legacy_file "$hash" "$path"; return; }
  for sub in "${_SYNC_CANONICAL_SUBFILES[@]}"; do
    _sync_out_one "$hash" "$sub" "$path/$sub.md"
  done
}

_sync_in_legacy_file() {
  local hash="$1" notes="$2" blob
  if blob=$(session_store_get "$hash" notes 2>/dev/null); then
    (umask 077 && printf '%s' "$blob" > "$notes"); return 0
  fi
  [[ -f "$notes" ]] && return 0
  local tmpl; tmpl=$(_sync_template_path)
  (umask 077 && mkdir -p "$(dirname "$notes")") 2>/dev/null
  (umask 077 && cp "$tmpl" "$notes")
}

_sync_out_legacy_file() {
  local hash="$1" notes="$2"
  [[ -f "$notes" ]] || return 0
  session_store_put "$hash" notes "$notes" && return 0
  _sync_out_failure_log "$hash" "$notes"
}

_sync_out_failure_log() {
  local input='{"tool_input":{"subagent_type":"session-memory-updater"}}'
  local resolved; resolved=$(printf '{"hash":"%s","notes":"%s","status":"put_failed"}' "$1" "$2")
  printf '[session-store] sync_out put failed for %s — see metrics jsonl\n' "$1" >&2
  bash "$_SESSION_STORE_LIB/log-injection.sh" "$input" "$resolved" "session-store-sync" "session-store-mirror.jsonl" 2>/dev/null || true
}
