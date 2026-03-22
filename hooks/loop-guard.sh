#!/usr/bin/env bash
# Re-entrancy loop guard — source this and call check_loop_guard "hook-name".
# Returns 1 (skip) if the named hook has fired more than MAX_CALLS times in WINDOW_SECS.
# Prevents infinite hook loops in pathological agent behaviour.
check_loop_guard() {
  local hook_name="$1"
  local max_calls="${2:-10}"
  local window_secs="${3:-60}"
  local guard_dir="/tmp/claude-hook-guard"
  local guard_file="${guard_dir}/${hook_name}"
  mkdir -p "$guard_dir"
  local now
  now=$(date +%s)
  local cutoff=$(( now - window_secs ))
  # Append current timestamp
  echo "$now" >> "$guard_file"
  # Count calls within window
  local count
  count=$(awk -v cutoff="$cutoff" '$1 >= cutoff' "$guard_file" | wc -l | tr -d ' ')
  # Trim file to only entries within window
  awk -v cutoff="$cutoff" '$1 >= cutoff' "$guard_file" > "${guard_file}.tmp" \
    && mv "${guard_file}.tmp" "$guard_file"
  if [[ "$count" -gt "$max_calls" ]]; then
    echo "LOOP GUARD: hook '$hook_name' has fired $count times in ${window_secs}s — skipping to prevent loop" >&2
    return 1
  fi
  return 0
}
