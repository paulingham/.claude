#!/usr/bin/env bats
# test_mutation_score_gate.bats — C5: mutation-score-gate.sh advisory-log hook
# Tests assertions per plan r2 enumerated list (7 total).

setup() {
  HOOK_PATH="$BATS_TEST_DIRNAME/../../hooks/mutation-score-gate.sh"
  SKILL_PATH="$BATS_TEST_DIRNAME/../../skills/mutation-score-report/SKILL.md"
  HOOKS_JSON="$BATS_TEST_DIRNAME/../../hooks/hooks.json"
  SETTINGS_JSON="$BATS_TEST_DIRNAME/../../settings.json"
  # Use CLAUDE_PLUGIN_DATA so harness-paths.sh resolves HARNESS_DATA to our temp dir.
  export CLAUDE_PLUGIN_DATA="$(mktemp -d)"
  export HARNESS_DATA="$CLAUDE_PLUGIN_DATA"
  export CLAUDE_HOOK_PROFILE="standard"
}

teardown() {
  rm -rf "${CLAUDE_PLUGIN_DATA:-}"
}

# --- (1) fail-open on garbage/empty stdin ---
@test "exit 0 on garbage/empty stdin" {
  run bash "$HOOK_PATH" <<< ""
  [ "$status" -eq 0 ]
}

@test "exit 0 on non-JSON garbage stdin" {
  run bash "$HOOK_PATH" <<< "this is not json at all !!!"
  [ "$status" -eq 0 ]
}

# --- (2) advisory: never exit 2 even on enforcing-trigger payload ---
@test "exit 0 on valid software-engineer payload — advisory never blocks" {
  local payload
  payload=$(jq -n \
    --arg sid "abc123" \
    --arg tid "my-task" \
    --arg role "software-engineer" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false, changed_files: ["hooks/foo.sh"]}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
}

# --- (3) early-exit + no write when role not in allowed set ---
@test "exit 0 and no write for excluded agent role code-reviewer" {
  local payload
  payload=$(jq -n \
    --arg sid "sess-excluded" \
    --arg tid "task-x" \
    --arg role "code-reviewer" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  [ ! -d "${HARNESS_DATA}/metrics/sess-excluded" ]
}

@test "exit 0 and no write for excluded agent role architect" {
  local payload
  payload=$(jq -n \
    --arg sid "sess-arch" \
    --arg tid "task-y" \
    --arg role "architect" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  [ ! -d "${HARNESS_DATA}/metrics/sess-arch" ]
}

# --- (4) valid payload writes mutation-score.jsonl under sanitized session dir ---
@test "software-engineer payload writes mutation-score.jsonl under sanitized session dir" {
  local sid="validSess-001"
  local payload
  payload=$(jq -n \
    --arg sid "$sid" \
    --arg tid "task-001" \
    --arg role "software-engineer" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false, changed_files: ["hooks/foo.sh", "hooks/bar.sh"]}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  [ -f "${HARNESS_DATA}/metrics/${sid}/mutation-score.jsonl" ]
}

@test "fix-engineer payload writes mutation-score.jsonl" {
  local sid="fixSess-002"
  local payload
  payload=$(jq -n \
    --arg sid "$sid" \
    --arg tid "task-002" \
    --arg role "fix-engineer" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  [ -f "${HARNESS_DATA}/metrics/${sid}/mutation-score.jsonl" ]
}

@test "path-traversal session_id is sanitized to unknown — no traversal write" {
  local payload
  payload=$(jq -n \
    --arg sid "../../../etc/traversal" \
    --arg tid "task-trav" \
    --arg role "software-engineer" \
    '{session_id: $sid, task_id: $tid, subagent_type: $role,
      stop_hook_active: false}')
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  # Must not write to a traversed path
  [ ! -f "/etc/traversal/mutation-score.jsonl" ]
  # Must write to sanitized fallback 'unknown'
  [ -f "${HARNESS_DATA}/metrics/unknown/mutation-score.jsonl" ]
}

# --- (5) header contains promotion-criterion tokens ---
@test "hook header contains >=10 sessions promotion criterion" {
  run grep -c ">=10" "$HOOK_PATH"
  [ "$status" -eq 0 ]
  [ "$output" -gt 0 ]
}

@test "hook header contains sessions token in promotion criterion" {
  run grep "sessions" "$HOOK_PATH"
  [ "$status" -eq 0 ]
}

@test "hook header contains 70% threshold in promotion criterion" {
  run grep "70%" "$HOOK_PATH"
  [ "$status" -eq 0 ]
}

# --- (6) skills/mutation-score-report/SKILL.md exists and references mutation-score.jsonl ---
@test "skills/mutation-score-report/SKILL.md exists" {
  [ -f "$SKILL_PATH" ]
}

@test "SKILL.md references mutation-score.jsonl" {
  run grep -c "mutation-score.jsonl" "$SKILL_PATH"
  [ "$status" -eq 0 ]
  [ "$output" -gt 0 ]
}

# --- (7) registered in BOTH hooks.json AND settings.json SubagentStop blocks ---
@test "mutation-score-gate.sh registered in hooks.json SubagentStop" {
  run python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
hooks_section = data.get("hooks", {})
stop_entries = hooks_section.get("SubagentStop", [])
for entry_group in stop_entries:
    for hook in entry_group.get("hooks", []):
        for arg in hook.get("args", []):
            if "mutation-score-gate.sh" in arg:
                sys.exit(0)
sys.exit(1)
PYEOF
  [ "$status" -eq 0 ]
}

@test "mutation-score-gate.sh registered in settings.json SubagentStop" {
  run python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
hooks_section = data.get("hooks", {})
stop_entries = hooks_section.get("SubagentStop", [])
for entry_group in stop_entries:
    for hook in entry_group.get("hooks", []):
        for arg in hook.get("args", []):
            if "mutation-score-gate.sh" in arg:
                sys.exit(0)
sys.exit(1)
PYEOF
  [ "$status" -eq 0 ]
}
