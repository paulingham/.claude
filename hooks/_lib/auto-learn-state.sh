#!/usr/bin/env bash
# Auto-learn gate state helpers. Shape: <=5 lines/func, <=50 lines/file.
# State file schema:
#   last_learn_run, pipelines_since_learn, observations_since_learn,
#   last_fired_pipeline_id, last_observation_offset

_als_default_state() {
  printf '%s' '{"last_learn_run":null,"pipelines_since_learn":0,"observations_since_learn":0,"last_fired_pipeline_id":null,"last_observation_offset":0}'
}

_als_read_state() {
  local f="$1"
  [[ -s "$f" ]] && cat "$f" || _als_default_state
}

_als_write_state() {
  local f="$1" json="$2" tmp="$1.tmp.$$"
  printf '%s\n' "$json" > "$tmp" && mv "$tmp" "$f"
}

_als_file_size() {
  [[ -f "$1" ]] || { echo 0; return; }
  wc -c < "$1" | tr -d ' '
}

_als_count_pipeline_records() {
  local f="$1" off="$2"
  [[ -s "$f" ]] || { echo 0; return; }
  tail -c "+$(( off + 1 ))" "$f" 2>/dev/null | \
    jq -r 'select(.record_type=="pipeline" or (has("pipeline_id") and has("phases") and (.record_type // "") != "tool_use")) | .pipeline_id // "unknown"' 2>/dev/null
}

_als_latest_pipeline_id() {
  local f="$1" off="$2"
  [[ -s "$f" ]] || { echo ""; return; }
  tail -c "+$(( off + 1 ))" "$f" 2>/dev/null | \
    jq -r 'select(.record_type=="pipeline" or (has("pipeline_id") and has("phases"))) | .pipeline_id' 2>/dev/null | tail -1
}
