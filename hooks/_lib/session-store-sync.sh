#!/usr/bin/env bash
# Sync helpers — Slice 4 fills in real round-trip; Slice 1 ships byte-no-op for local.

_sync_template_path() {
  printf '%s\n' "$_SESSION_STORE_ROOT/session-memory/config/template.md"
}

_sync_stamp_template() {
  local target="$1"; local tmpl; tmpl=$(_sync_template_path)
  mkdir -p "$(dirname "$target")" 2>/dev/null
  (umask 077 && cp "$tmpl" "$target")
}

session_memory_sync_in() {
  local hash="$1" notes="$2" backend blob; backend=$(_resolve_backend)
  [[ "$backend" = "local" ]] && return 0
  if blob=$(session_store_get "$hash" notes 2>/dev/null); then
    (umask 077 && printf '%s' "$blob" > "$notes"); return 0
  fi
  [[ -f "$notes" ]] && return 0
  _sync_stamp_template "$notes"
}

session_memory_sync_out() {
  local hash="$1" notes="$2" backend; backend=$(_resolve_backend)
  [[ "$backend" = "local" ]] && return 0
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
