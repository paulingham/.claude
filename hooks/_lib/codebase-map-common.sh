#!/usr/bin/env bash
# Shared helpers used by hooks/codebase-map-rebuild.sh AND
# hooks/codebase-map-poll.sh. Source this file AFTER log.sh +
# project-hash.sh + codebase-map-flock.sh — the helpers below assume
# those are loaded.
#
# DRY: the rebuild + poll hooks share most lifecycle logic (hash
# resolution, metrics path setup, count + cache-hit-rate stubs,
# subprocess invocation). Putting that logic here is the 2nd-occurrence
# extraction per `protocols/engineering-invariants.md` § Code Shape.

# ---- hash + paths ---------------------------------------------------

# Resolve project hash with AC15 env-first / AC20 regex validation.
# Echoes the resolved hash (or "local" fallback). Never fails.
_cbm_resolve_hash() {
  local lib_dir="$1" raw_hash="${CLAUDE_PROJECT_HASH:-}"
  local hash
  hash="$(/usr/bin/env python3 "$lib_dir/codebase-map-state.py" validate-hash "$raw_hash" 2>/dev/null || echo "local")"
  if [[ "$hash" == "local" && -z "$raw_hash" ]]; then
    hash=$(_project_hash --fallback "local")
  fi
  echo "$hash"
}

# Sanitise CLAUDE_SESSION_ID for use as a metrics-dir component.
_cbm_session_id() {
  local raw="${CLAUDE_SESSION_ID:-local-$$}"
  raw="${raw//[^A-Za-z0-9_-]/_}"
  [[ -z "$raw" || "$raw" =~ ^_+$ ]] && raw="local-$$"
  echo "$raw"
}

# ---- file count + cache hit rate -----------------------------------

# Count supported source files under the given root.
_cbm_count_files() {
  local root="$1"
  [[ -d "$root" ]] || { echo 0; return; }
  /usr/bin/find "$root" -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.rb' -o -name '*.go' \) 2>/dev/null | /usr/bin/wc -l | /usr/bin/tr -d ' '
}

# Map subprocess return code → cache_hit_rate float.
# Without finer telemetry from the CLI today, success → 1.0 (warm
# cache assumption), failure → 0.0.
_cbm_cache_hit_rate() {
  local rc="$1"
  [[ "$rc" -eq 0 ]] && echo "1.0" || echo "0.0"
}

# ---- subprocess invocation + JSONL emission -------------------------

# Run the codebase_map.cli build subprocess and emit one JSONL line.
# Args: lib_dir hook_label repo_root cache_dir metrics_file sha_before sha_after
#
# AC18: argv form via subprocess; inline import-from-bash is forbidden,
# so shell-into-Python via the dash-c flag must NEVER be used here.
# AC21: non-zero rc treated as graceful degradation.
_cbm_invoke_and_emit() {
  local lib_dir="$1" hook_label="$2" repo_root="$3" cache_dir="$4"
  local metrics_file="$5" sha_before="$6" sha_after="$7"
  local cli_module="${CLAUDE_CODEBASE_MAP_CLI_MODULE:-codebase_map.cli}"
  local started_ns ended_ns time_ms rc file_count cache_hit_rate
  started_ns=$(/bin/date +%s%N)
  /usr/bin/env python3 -m "$cli_module" build "$repo_root" "$cache_dir" >/dev/null 2>&1
  rc=$?
  ended_ns=$(/bin/date +%s%N)
  time_ms=$(( (ended_ns - started_ns) / 1000000 ))
  if [[ $rc -ne 0 ]]; then
    printf 'codebase-map: %s skipped (cli rc=%d, cache holds prior result)\n' "$hook_label" "$rc" >&2
  fi
  file_count=$(_cbm_count_files "$repo_root")
  cache_hit_rate=$(_cbm_cache_hit_rate "$rc")
  /usr/bin/env python3 "$lib_dir/codebase_map_emit.py" \
    --metrics-file "$metrics_file" \
    --hook "$hook_label" \
    --file-count "$file_count" \
    --time-ms "$time_ms" \
    --cache-hit-rate "$cache_hit_rate" \
    --sha-before "$sha_before" \
    --sha-after "$sha_after" 2>/dev/null || true
}
