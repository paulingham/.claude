#!/usr/bin/env bash
# Codebase-map Stop poll hook. Reads cached `last_built_sha` and runs
# `git rev-parse main`; rebuilds only when the SHA advances. Reuses the
# rebuild-side flock to serialize against the SessionStart hook. Always
# exits 0 (subprocess-isolates the generator per AC18, degrades on
# AC21 catch surface).
#
# enforces: rules/_detail/autonomous-intelligence.md:Codebase Map
# protects: codebase-map-poll

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT    # MUST register BEFORE the disable check

[[ "${CLAUDE_DISABLE_CODEBASE_MAP:-0}" == "1" ]] && exit 0
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

LIB_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib"
# shellcheck disable=SC1091
source "$LIB_DIR/project-hash.sh"
# shellcheck disable=SC1091
source "$LIB_DIR/codebase-map-flock.sh"

# AC15 + AC20: env-first, regex-validated.
RAW_HASH="${CLAUDE_PROJECT_HASH:-}"
HASH="$(/usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" validate-hash "$RAW_HASH" 2>/dev/null || echo "local")"
if [[ "$HASH" == "local" && -z "$RAW_HASH" ]]; then
  HASH=$(_project_hash --fallback "local")
fi

CACHE_DIR="$HOME/.claude/db/codebase-map/$HASH"
STATE_FILE="$CACHE_DIR/state.json"
SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
METRICS_FILE="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}/$SESSION/codebase-map-rebuild.jsonl"
mkdir -p "$CACHE_DIR" "$(dirname "$METRICS_FILE")"

REPO_ROOT="${CLAUDE_CODEBASE_MAP_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SHA_BEFORE="$(/usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" read "$STATE_FILE" --field last_built_sha 2>/dev/null || echo "")"
SHA_AFTER="$(/usr/bin/git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "")"

# AC17: no-op when SHA unchanged.
if [[ -n "$SHA_BEFORE" && "$SHA_BEFORE" == "$SHA_AFTER" ]]; then
  exit 0
fi

# Persist new SHA BEFORE rebuild (state-before-expensive-op).
[[ -n "$SHA_AFTER" ]] && /usr/bin/env python3 "$LIB_DIR/codebase-map-state.py" write "$STATE_FILE" "$SHA_AFTER" 2>/dev/null || true

_cbm_poll_rebuild() {
  # AC18 contract: invocation is `python3 -m codebase_map.cli build <root> <cache>`
  # (argv form via subprocess; inline import-from-bash is forbidden, so
  # shell-into-Python via the dash-c flag must NEVER be used here).
  local cli_module="${CLAUDE_CODEBASE_MAP_CLI_MODULE:-codebase_map.cli}"
  local started_ns ended_ns file_count cache_hit_rate
  started_ns=$(/bin/date +%s%N)
  /usr/bin/env python3 -m "$cli_module" build "$REPO_ROOT" "$CACHE_DIR" >/dev/null 2>&1
  local rc=$?
  ended_ns=$(/bin/date +%s%N)
  local time_ms=$(( (ended_ns - started_ns) / 1000000 ))
  if [[ $rc -ne 0 ]]; then
    printf 'codebase-map: poll-rebuild skipped (cli rc=%d, cache holds prior result)\n' "$rc" >&2
  fi
  file_count=$(_cbm_count_files "$REPO_ROOT")
  cache_hit_rate=$(_cbm_cache_hit_rate "$rc")
  /usr/bin/env python3 "$LIB_DIR/codebase_map_emit.py" \
    --metrics-file "$METRICS_FILE" \
    --hook "poll" \
    --file-count "$file_count" \
    --time-ms "$time_ms" \
    --cache-hit-rate "$cache_hit_rate" \
    --sha-before "$SHA_BEFORE" \
    --sha-after "$SHA_AFTER" 2>/dev/null || true
}

_cbm_count_files() {
  local root="$1"
  [[ -d "$root" ]] || { echo 0; return; }
  /usr/bin/find "$root" -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.rb' -o -name '*.go' \) 2>/dev/null | /usr/bin/wc -l | /usr/bin/tr -d ' '
}

_cbm_cache_hit_rate() {
  local rc="$1"
  [[ "$rc" -eq 0 ]] && echo "1.0" || echo "0.0"
}

with_codebase_map_lock "$HASH" -- _cbm_poll_rebuild
exit 0
