#!/usr/bin/env bash
# Re-entrancy loop guard — source this and call check_loop_guard "hook-name".
# Returns 1 (skip) if the named hook has fired more than MAX_CALLS times in WINDOW_SECS.
# Prevents infinite hook loops in pathological agent behaviour.
# Also provides check_stuck() — semantic stuck-detector (advisory, always returns 0).
# shellcheck source=_lib/state-dir.sh
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
check_loop_guard() {
  local hook_name="$1"
  local max_calls="${2:-10}"
  local window_secs="${3:-60}"
  local guard_dir; guard_dir=$(_state_path "hook-guard")
  local guard_file="${guard_dir}/${hook_name}"
  mkdir -p -m 700 "$guard_dir"
  local now
  now=$(date +%s)
  local cutoff=$(( now - window_secs ))
  # Append current timestamp
  echo "$now" >> "$guard_file"
  # Count calls within window
  local count
  count=$(awk -v cutoff="$cutoff" '$1 >= cutoff' "$guard_file" | wc -l | tr -d ' ')
  # Trim file to only entries within window (mktemp prevents symlink attacks)
  local tmpfile
  tmpfile=$(mktemp "${guard_dir}/${hook_name}.tmp.XXXXXX")
  awk -v cutoff="$cutoff" '$1 >= cutoff' "$guard_file" > "$tmpfile" \
    && mv "$tmpfile" "$guard_file" \
    || rm -f "$tmpfile"
  if [[ "$count" -gt "$max_calls" ]]; then
    echo "LOOP GUARD: hook '$hook_name' has fired $count times in ${window_secs}s — skipping to prevent loop" >&2
    return 1
  fi
  return 0
}

# check_stuck STOP_STDIN_JSON
# Runs the semantic stuck-detector against the transcript named in the Stop hook payload.
# ADVISORY: emits telemetry + stderr note on MATCH; always returns 0 (never blocks).
check_stuck() {
  local input="$1"
  local hook_dir; hook_dir="$(dirname "${BASH_SOURCE[0]}")"
  local detector="${hook_dir}/_lib/stuck-detector.py"
  [[ -f "$detector" ]] || return 0
  local result
  result=$(printf '%s' "$input" | python3 "$detector" 2>/dev/null) || return 0
  [[ "$result" == MATCH* ]] || return 0
  local pattern; pattern=$(printf '%s' "$result" | awk '{print $2}')
  local evidence; evidence=$(printf '%s' "$result" | cut -f2-)
  echo "STUCK-DETECTOR [advisory]: pattern '$pattern' detected — session may be looping" >&2
  _emit_stuck_telemetry "$pattern" "$evidence"
  # TODO(promotion): replace return 0 below with exit 2 in the blocking branch after
  # advisory period ends and promotion criterion is met. Mirror the comment style in
  # hooks/verification-freshness-guard.sh:33-34.
  return 0
}

# _emit_stuck_telemetry PATTERN EVIDENCE_JSON
# Writes one JSONL line to $HARNESS_DATA/metrics/{session}/stuck-detector.jsonl.
_emit_stuck_telemetry() {
  local pattern="$1" evidence="$2"
  local session="${CLAUDE_SESSION_ID:-local-$$}"
  session="${session//[^A-Za-z0-9_-]/_}"
  local dir="${HARNESS_DATA}/metrics/${session}"
  mkdir -p "$dir" 2>/dev/null || return 0
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "unknown")
  printf '{"timestamp":"%s","source":"stuck-advisory","pattern":"%s","evidence":%s,"session":"%s"}\n' \
    "$ts" "$pattern" "$evidence" "$session" >> "$dir/stuck-detector.jsonl" 2>/dev/null
}
