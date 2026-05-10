#!/usr/bin/env bash
# AC26-AC28 — Codebase-map DUAL_PATH divergence + fallback JSONL emitters.
#
# The codebase-map sub-file has TWO possible sources during the 30-day
# DUAL_PATH soak:
#
#   Generator path: ~/.claude/db/codebase-map/{hash}/codebase-map.md
#                   — written by codebase_map.cli build (Slice C hook).
#   Manual path:    ~/.claude/session-memory/{hash}/codebase-map.md
#                   — historical/hand-authored sub-file.
#
# The reader (session-memory-read-split.sh) prefers the generator path.
# This file ships two emitters that record forensic JSONL lines so an
# operator can audit divergences during the soak window:
#
#   codebase_map_emit_fallback   — generator absent, manual served.
#   codebase_map_emit_divergence — both present, content differs.
#
# Both emitters delegate to log-injection.sh so emission goes through the
# same printf-injection-safe path used by every other JSONL forensic
# stream (memory: instinct-jsonl-log-injection-printf).
#
# Public API:
#   codebase_map_short_hash <file>
#       — print first-16-chars sha256 hex of file contents. Empty/missing
#         file → empty string. Never fails.
#   codebase_map_emit_fallback   <hash> <subfile>
#       — emit one JSONL line with source: "codebase-map-fallback".
#   codebase_map_emit_divergence <hash> <subfile> <gen_file> <man_file>
#       — emit one JSONL line with source: "codebase-map-divergence" AND
#         a content-hash pair (no full content — privacy + size).
#
# enforces: rules/_detail/autonomous-intelligence.md:Codebase Map
# protects: session-memory-read-split

_CMD_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CMD_DIVERGENCE_FILE="codebase-map-divergence.jsonl"

# Build a JSON object from alternating key/value pairs. Used for the
# `resolved` payload of log-injection.sh. Routed through Python json.dumps
# (memory: instinct-jsonl-log-injection-printf) so values are escaped
# safely even when they contain quotes or control characters.
_cmd_jsonl_resolved() {
  /usr/bin/env python3 -c '
import json, sys
items = sys.argv[1:]
print(json.dumps(dict(zip(items[0::2], items[1::2]))))
' "$@" 2>/dev/null
}

# Emit one JSONL line via log-injection.sh. Internal helper.
_cmd_emit() {
  local source_label="$1" resolved="$2"
  bash "$_CMD_LIB_DIR/log-injection.sh" \
    '{"tool_input":{}}' "$resolved" \
    "$source_label" "$_CMD_DIVERGENCE_FILE" 2>/dev/null || true
}

# Print the 16-char short sha256 of the file contents. Missing/unreadable
# file prints the empty string — never fails the caller.
codebase_map_short_hash() {
  local file="$1"
  [[ -f "$file" ]] || { echo ""; return 0; }
  /usr/bin/env python3 -c '
import hashlib, sys
try:
    print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest()[:16])
except OSError:
    print("")
' "$file" 2>/dev/null || echo ""
}

# Emit one JSONL line: source="codebase-map-fallback" carrying the hash
# + sub_file pair. Used when the generator path is missing and the reader
# served the manual file. Never fails the caller.
codebase_map_emit_fallback() {
  local hash="$1" sub="$2" resolved
  resolved=$(_cmd_jsonl_resolved project_hash "$hash" sub_file "$sub") || return 0
  _cmd_emit "codebase-map-fallback" "$resolved"
}

# Emit one JSONL line: source="codebase-map-divergence" carrying the
# hash + sub_file + content-hash pair (NO full content — privacy + size).
# Used when both files are present and content differs. Never fails the
# caller.
codebase_map_emit_divergence() {
  local hash="$1" sub="$2" gen_file="$3" man_file="$4"
  local gen_hash man_hash resolved
  gen_hash=$(codebase_map_short_hash "$gen_file")
  man_hash=$(codebase_map_short_hash "$man_file")
  resolved=$(_cmd_jsonl_resolved \
    project_hash            "$hash" \
    sub_file                "$sub" \
    content_hash_generator  "$gen_hash" \
    content_hash_manual     "$man_hash") || return 0
  _cmd_emit "codebase-map-divergence" "$resolved"
}
