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
# String fields in evidence are capped at 200 chars; full value stored as sha1_<field>.
_emit_stuck_telemetry() {
  local pattern="$1" evidence="$2"
  local session="${CLAUDE_SESSION_ID:-local-$$}"
  session="${session//[^A-Za-z0-9_-]/_}"
  [[ -z "$session" || "$session" =~ ^_+$ ]] && session="local-$$"
  local dir="${HARNESS_DATA}/metrics/${session}"
  # shellcheck disable=SC2174
  mkdir -p -m 700 "$dir" 2>/dev/null || return 0
  local ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "unknown")
  python3 - "$ts" "$pattern" "$evidence" "$session" >> "$dir/stuck-detector.jsonl" 2>/dev/null << 'PYEOF'
import json, hashlib, sys
ts, pattern, evidence_raw, session = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    ev = json.loads(evidence_raw)
except Exception:
    ev = {}
def cap(v):
    s = str(v) if not isinstance(v, str) else v
    return s[:200]
def cap_obj(o):
    if not isinstance(o, dict):
        return o
    out = {}
    for k, v in o.items():
        if isinstance(v, str) and len(v) > 200:
            out[k] = v[:200]
            out[f"sha1_{k}"] = "sha1:" + hashlib.sha1(v.encode()).hexdigest()
        elif isinstance(v, list):
            out[k] = [cap(i) for i in v]
        else:
            out[k] = v
    return out
print(json.dumps({"timestamp": ts, "source": "stuck-advisory",
                  "pattern": pattern, "evidence": cap_obj(ev), "session": session}))
PYEOF
}
