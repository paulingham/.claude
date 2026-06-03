#!/usr/bin/env bash
# Helper for hooks/bug-fixed-payload-validator.sh.
# Pure functions: classify payload shape, write JSONL audit line.
# enforces: protocols/verdict-catalog.md (BUG_FIXED row)
# Sourced by the SubagentStop hook only.

# Classify a transcript string against the BUG_FIXED/DEBUG_RESOLVED payload contract.
# Echoes one of: legacy mapping missing_red missing_green missing_path valid env_only no_verdict
# Args: $1 = transcript text (may be multiline), $2 = verdict (BUG_FIXED|DEBUG_RESOLVED|other)
_bfpv_classify() {
  local transcript="$1" verdict="$2"
  # env-only short-form
  if printf '%s' "$transcript" | grep -qE '^[[:space:]]*reproducer_artifact:[[:space:]]*env-only[[:space:]]*$'; then
    printf 'env_only'; return
  fi
  # Single-string legacy form: reproducer_artifact: <path>  (not followed by mapping keys)
  if printf '%s' "$transcript" | grep -qE '^[[:space:]]*reproducer_artifact:[[:space:]]*[^[:space:]]+[[:space:]]*$'; then
    printf 'legacy'; return
  fi
  # Mapping form — check sub-keys.
  local has_path has_red has_green
  has_path=$(printf '%s' "$transcript" | grep -cE '^[[:space:]]+path:' || true)
  has_red=$(printf '%s' "$transcript" | grep -cE '^[[:space:]]+red_evidence:' || true)
  has_green=$(printf '%s' "$transcript" | grep -cE '^[[:space:]]+green_evidence:' || true)
  if [[ "$has_path" -eq 0 && "$has_red" -eq 0 && "$has_green" -eq 0 ]]; then
    printf 'no_verdict'; return
  fi
  [[ "$has_red" -eq 0 ]]   && { printf 'missing_red';   return; }
  [[ "$has_green" -eq 0 ]] && { printf 'missing_green'; return; }
  [[ "$has_path" -eq 0 ]]  && { printf 'missing_path';  return; }
  printf 'valid'
}

# Map a shape to its strict-mode rejection message.
_bfpv_reject_message() {
  case "$1" in
    env_only)      printf 'env-only forbidden for BUG_FIXED (use DEBUG_RESOLVED for env-only justifications)' ;;
    missing_red)   printf 'missing required key: red_evidence' ;;
    missing_green) printf 'missing required key: green_evidence' ;;
    missing_path)  printf 'missing required key: path' ;;
    legacy)        printf 'missing required key: red_evidence (legacy string form deprecated)' ;;
    *)             printf 'missing required key: red_evidence' ;;
  esac
}

# Append one JSONL line. Args: $1 file, $2 task_id, $3 shape, $4 action.
_bfpv_emit_jsonl() {
  local file="$1" task_id="$2" shape="$3" action="$4"
  mkdir -p "$(dirname "$file")" 2>/dev/null || return 0
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # Build via jq so values containing `"` or newlines are JSON-escaped, not
  # injected raw into the JSONL stream.
  jq -cn \
    --arg ts "$ts" --arg task_id "$task_id" --arg shape "$shape" --arg action "$action" \
    '{timestamp:$ts,task_id:$task_id,payload_shape:$shape,action:$action}' \
    >> "$file" 2>/dev/null || true
}
