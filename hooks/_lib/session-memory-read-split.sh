#!/usr/bin/env bash
# AC5/AC10/AC16 — reader-fallback for the 30-day DUAL_PATH soak.
# session_memory_read_split <hash> <subfile>:
#   - prints {hash}/{subfile}.md when present (new layout)
#   - else extracts the matching canonical section from {hash}/notes.md
#   - exit 0 on hit, exit 1 on neither
# On legacy fallback, appends one JSONL line to
# metrics/{session-id}/session-store-mirror.jsonl.

_smr_config_dir() { printf '%s\n' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; }

_smr_canonical_header() {
  case "$1" in
    codebase-map) echo "# Codebase Map" ;;
    build-test)   echo "# Build & Test" ;;
    fragility)    echo "# Critical Paths" ;;
    active-work)  echo "# Active Work" ;;
    patterns)     echo "# Patterns & Conventions" ;;
    *)            return 1 ;;
  esac
}

_smr_extract_section() {
  local notes="$1" header="$2"
  awk -v h="$header" 'BEGIN{f=0} /^# /{ if(f)exit; if($0==h){f=1; next} } f{print}' "$notes"
}

_smr_emit_fallback_jsonl() {
  local hash="$1" sub="$2"
  bash "$(dirname "${BASH_SOURCE[0]}")/log-injection.sh" \
    '{"tool_input":{}}' \
    "$(printf '{"project_hash":"%s","sub_file":"%s"}' "$hash" "$sub")" \
    "session-memory-read-fallback" "session-store-mirror.jsonl" 2>/dev/null || true
}

_smr_read_legacy() {
  local hash="$1" sub="$2" notes="$3" header section
  header=$(_smr_canonical_header "$sub") || return 1
  section=$(_smr_extract_section "$notes" "$header") || return 1
  [[ -z "$section" ]] && return 1
  _smr_emit_fallback_jsonl "$hash" "$sub"
  printf '%s' "$section"
}

session_memory_read_split() {
  local hash="$1" sub="$2"
  local proj; proj="$(_smr_config_dir)/session-memory/$hash"
  local new="$proj/$sub.md" legacy="$proj/notes.md"
  [[ -f "$new" ]] && { cat "$new"; return 0; }
  [[ -f "$legacy" ]] && { _smr_read_legacy "$hash" "$sub" "$legacy"; return; }
  return 1
}
