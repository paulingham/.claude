#!/usr/bin/env bats
# Slice B — deploy-outcome-audit.sh E2E tests (CI-visible at tests/shell/)
# B1: non-Skill tool_name short-circuits (exit 0, no write)
# B2: Skill + [Deploy] marker appends one record
# B3: marker absent -> exit 0, no record
# B4: AUTO_ROLLBACK marker writes outcome AUTO_ROLLBACK
# B5: malformed/oversized marker capped, never crashes
# B5-cap-readback: out-of-enum valid-charset outcome stored as <unknown> through full hook path
# B5-missing-pipeline: marker with missing pipeline_id field -> exit 0, no record
# B5-idem: re-fire identical stdin -> two lines; consumer collapses to one

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/deploy-outcome-audit.sh"
  TMP_DIR="$(mktemp -d)"
  export CLAUDE_PLUGIN_DATA="$TMP_DIR"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="standard"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
}

teardown() {
  rm -rf "$TMP_DIR"
}

_make_skill_input() {
  local outcome="$1" pipeline_id="$2" environment="$3"
  # WHY: \n inside a JSON string must be the two-char escape sequence, not a
  # literal newline — jq rejects control chars and returns empty tool_response.
  printf '{"tool_name":"Skill","tool_response":"[Deploy] outcome: %s pipeline_id: %s environment: %s\\nDone.","session_id":"test-sid"}' \
    "$outcome" "$pipeline_id" "$environment"
}

_find_obs_jsonl() {
  find "$TMP_DIR/learning" -name "observations.jsonl" 2>/dev/null | head -1
}

@test "B1 non-Skill tool_name short-circuits: exit 0, no write" {
  local input='{"tool_name":"Write","tool_response":"done","session_id":"test-sid"}'
  run bash -c "printf '%s' '$input' | '$HOOK'"
  [ "$status" -eq 0 ]
  local obs
  obs=$(_find_obs_jsonl)
  [ -z "$obs" ]
}

@test "B2 Skill + DEPLOYED marker appends one record with correct fields" {
  _make_skill_input "DEPLOYED" "my-pipeline-123" "staging" | bash "$HOOK"

  local obs
  obs=$(_find_obs_jsonl)
  [ -n "$obs" ]
  local count
  count=$(wc -l < "$obs")
  [ "$count" -eq 1 ]

  local record
  record=$(head -1 "$obs")
  echo "$record" | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['record_type'] == 'deploy_outcome', r
assert r['outcome'] == 'DEPLOYED', r
assert r['pipeline_id'] == 'my-pipeline-123', r
assert r['environment'] == 'staging', r
assert 'timestamp' in r, r
"
}

@test "B3 marker absent -> exit 0, no record" {
  local input='{"tool_name":"Skill","tool_response":"Phase complete, no marker here.","session_id":"test-sid"}'
  run bash -c "printf '%s' '$input' | '$HOOK'"
  [ "$status" -eq 0 ]
  local obs
  obs=$(_find_obs_jsonl)
  [ -z "$obs" ]
}

@test "B4 AUTO_ROLLBACK marker writes outcome AUTO_ROLLBACK" {
  _make_skill_input "AUTO_ROLLBACK" "pipe-rollback-99" "production" | bash "$HOOK"

  local obs
  obs=$(_find_obs_jsonl)
  [ -n "$obs" ]

  local record
  record=$(head -1 "$obs")
  echo "$record" | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['outcome'] == 'AUTO_ROLLBACK', r
assert r['pipeline_id'] == 'pipe-rollback-99', r
assert r['environment'] == 'production', r
"
}

@test "B5 oversized field capped, hook never crashes (exit 0)" {
  local big_outcome
  big_outcome=$(python3 -c "print('X' * 3000)")
  local input
  input=$(printf '{"tool_name":"Skill","tool_response":"[Deploy] outcome: %s pipeline_id: p1 environment: staging","session_id":"sid"}' \
    "$big_outcome")
  run bash -c "printf '%s' '$input' | '$HOOK'"
  [ "$status" -eq 0 ]
}

@test "B5-cap-readback out-of-enum valid-charset outcome stored as <unknown> through full hook path" {
  # WHY: B5 only proved exit 0; this confirms the full path actually writes a
  # record and that _safe_outcome maps any non-enum value to <unknown> —
  # the E2E gap flagged in code-review.
  local input
  input='{"tool_name":"Skill","tool_response":"[Deploy] outcome: FOOBAR pipeline_id: pipe-x environment: staging","session_id":"sid"}'
  printf '%s' "$input" | bash "$HOOK"

  local obs
  obs=$(_find_obs_jsonl)
  [ -n "$obs" ]

  local record
  record=$(head -1 "$obs")
  echo "$record" | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['record_type'] == 'deploy_outcome', r
assert r['outcome'] == '<unknown>', f'expected <unknown>, got {r[\"outcome\"]}'
assert r['pipeline_id'] == 'pipe-x', r
"
}

@test "B5-missing-pipeline marker with empty pipeline_id field exits 0 with no record" {
  # WHY: the bash hook regex requires [A-Za-z0-9._-]+ (1+ chars) for each field;
  # a marker with a missing/empty pipeline_id value fails to match and exits 0 safely.
  local input='{"tool_name":"Skill","tool_response":"[Deploy] outcome: DEPLOYED pipeline_id:  environment: staging","session_id":"sid"}'
  run bash -c "printf '%s' '$input' | '$HOOK'"
  [ "$status" -eq 0 ]
  local obs
  obs=$(_find_obs_jsonl)
  [ -z "$obs" ]
}

@test "B5-idem hook stateless: re-fire identical stdin produces two records; consumer collapses to one" {
  local input
  input=$(_make_skill_input "DEPLOYED" "idem-pipeline" "staging")

  printf '%s' "$input" | bash "$HOOK"
  printf '%s' "$input" | bash "$HOOK"

  local obs
  obs=$(_find_obs_jsonl)
  [ -n "$obs" ]
  local count
  count=$(wc -l < "$obs")
  [ "$count" -eq 2 ]

  # consumer collapse: MAX-timestamp per pipeline_id -> 1 effective record
  local effective
  effective=$(python3 -c "
import json, sys
records = [json.loads(l) for l in open('$obs')]
by_pipeline = {}
for r in records:
    pid = r.get('pipeline_id', '')
    ts  = r.get('timestamp', '')
    if pid not in by_pipeline or ts > by_pipeline[pid]['timestamp']:
        by_pipeline[pid] = r
print(len(by_pipeline))
")
  [ "$effective" -eq 1 ]
}
