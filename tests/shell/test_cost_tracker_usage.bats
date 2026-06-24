#!/usr/bin/env bats
# ATDD tests — cost-tracker.sh writes usage_by_model into session_end records.
#
# AC3: given a Stop stdin with transcript_path → fixture, the session_end
#      record in costs.jsonl carries a usage_by_model object with summed
#      per-model token counts AND still has the pre-existing fields.
# AC4: missing/bad transcript_path → hook still exit 0, writes record
#      (fail-open regression).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/cost-tracker.sh"
  TMP="$(mktemp -d -t ctu.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="standard"
  mkdir -p "$TMP/.claude/metrics"
  COSTS="$TMP/.claude/metrics/costs.jsonl"
  unset CLAUDE_CONFIG_DIR CLAUDE_PLUGIN_DATA
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_make_transcript() {
  # Write a minimal transcript JSONL to $1 with 2 assistant records across 2 models.
  local path="$1"
  cat > "$path" << 'EOF'
{"type":"assistant","message":{"model":"claude-opus-4-8","usage":{"input_tokens":1000,"output_tokens":200,"cache_read_input_tokens":500,"cache_creation_input_tokens":100}}}
{"type":"assistant","message":{"model":"claude-sonnet-4-6","usage":{"input_tokens":300,"output_tokens":50,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
{"type":"assistant","message":{"model":"claude-opus-4-8","usage":{"input_tokens":400,"output_tokens":80,"cache_read_input_tokens":200,"cache_creation_input_tokens":50}}}
EOF
}

@test "AC3: session_end record contains usage_by_model when transcript_path is valid" {
  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  echo "$input" | bash "$HOOK"
  [ -f "$COSTS" ]
  grep -q '"usage_by_model"' "$COSTS"
}

@test "AC3: usage_by_model contains summed opus-4-8 input_tokens=1400" {
  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  echo "$input" | bash "$HOOK"
  # Total opus input = 1000 + 400 = 1400
  jq -e '."usage_by_model"."claude-opus-4-8".input_tokens == 1400' "$COSTS" >/dev/null
}

@test "AC3: usage_by_model contains sonnet-4-6 with input_tokens=300" {
  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  echo "$input" | bash "$HOOK"
  jq -e '."usage_by_model"."claude-sonnet-4-6".input_tokens == 300' "$COSTS" >/dev/null
}

@test "AC3: pre-existing fields preamble_tokens, duration_s, tool_calls still present" {
  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  echo "$input" | bash "$HOOK"
  grep -qE '"preamble_tokens":[0-9]+' "$COSTS"
  grep -qE '"duration_s":[0-9]+' "$COSTS"
  grep -qE '"tool_calls":[0-9]+' "$COSTS"
}

@test "AC4: missing transcript_path → exit 0, record still written (fail-open)" {
  run bash -c "printf '{\"stop_hook_active\":false}' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$COSTS" ]
  grep -q '"event":"session_end"' "$COSTS"
}

@test "AC4: bad transcript_path (non-existent file) → exit 0, record written" {
  run bash -c "printf '{\"stop_hook_active\":false,\"transcript_path\":\"/nonexistent/file.jsonl\"}' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$COSTS" ]
  grep -q '"event":"session_end"' "$COSTS"
}

@test "AC4: garbage transcript → exit 0, record written without crashing" {
  local tp="$TMP/garbage.jsonl"
  printf 'NOT JSON\n{{{{GARBAGE}}}}\n' > "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$COSTS" ]
  grep -q '"event":"session_end"' "$COSTS"
}

@test "AC3-b: usage_by_model is valid JSON object (parseable by jq)" {
  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")
  echo "$input" | bash "$HOOK"
  jq -e '.usage_by_model | type == "object"' "$COSTS" >/dev/null
}

@test "AC5: usage_by_model NON-EMPTY when transcript_usage.py runs under /usr/bin/python3" {
  # A6: drive cost-tracker.sh with python3 shimmed to /usr/bin/python3 via PATH wrapper.
  # Verifies that PEP-604 fix works end-to-end through the hook's _ct_read_usage path.
  # Skips with explicit marker when /usr/bin/python3 is absent or is >= 3.10.
  local PROD_PY="/usr/bin/python3"
  if [ ! -f "$PROD_PY" ]; then
    skip "skip: no <3.10 interpreter available; static guard A1 still gates"
  fi
  local py_version
  py_version=$("$PROD_PY" -c "import sys; print(1 if sys.version_info < (3, 10) else 0)" 2>/dev/null || echo "0")
  if [ "$py_version" != "1" ]; then
    skip "skip: no <3.10 interpreter available; static guard A1 still gates"
  fi

  # Build a PATH-shim dir so the hook's bare `python3` call resolves to /usr/bin/python3.
  local SHIM_DIR="$TMP/shim_bin"
  mkdir -p "$SHIM_DIR"
  cat > "$SHIM_DIR/python3" << SHIMEOF
#!/usr/bin/env bash
exec "$PROD_PY" "\$@"
SHIMEOF
  chmod +x "$SHIM_DIR/python3"

  local tp="$TMP/transcript.jsonl"
  _make_transcript "$tp"
  local input
  input=$(printf '{"stop_hook_active":false,"transcript_path":"%s"}' "$tp")

  echo "$input" | PATH="$SHIM_DIR:$PATH" bash "$HOOK"
  [ -f "$COSTS" ]
  local usage
  usage=$(jq -r '.usage_by_model | keys | length' "$COSTS")
  # Non-empty: at least 1 model key present
  [ "$usage" -gt 0 ]
}
