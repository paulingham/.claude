#!/usr/bin/env bats
# test_arch_fitness_gate.bats — arch-fitness-gate.sh advisory SubagentStop hook
# B1-B6: runtime behaviour; C1-C3: registration + executable

setup() {
  HOOK_PATH="$BATS_TEST_DIRNAME/../../hooks/arch-fitness-gate.sh"
  HOOKS_JSON="$BATS_TEST_DIRNAME/../../hooks/hooks.json"
  SETTINGS_JSON="$BATS_TEST_DIRNAME/../../settings.json"
  export CLAUDE_PLUGIN_DATA="$(mktemp -d)"
  export HARNESS_DATA="$CLAUDE_PLUGIN_DATA"
  export CLAUDE_HOOK_PROFILE="standard"
  # Point HARNESS_ROOT at the repo so the hook can locate _lib and arch_fitness_cli.py
  export CLAUDE_PLUGIN_ROOT="$BATS_TEST_DIRNAME/../.."
}

teardown() {
  rm -rf "${CLAUDE_PLUGIN_DATA:-}"
}

# B1 — empty stdin → status 0 (fail-open)
@test "B1: empty stdin exits 0" {
  run bash "$HOOK_PATH" <<< ""
  [ "$status" -eq 0 ]
}

# B2 — cyclic _lib fixture → status 0 AND stderr contains 'cycle'
@test "B2: cyclic lib dir exits 0 and emits cycle advisory on stderr" {
  local lib_dir
  lib_dir="$(mktemp -d)"
  echo "import b_mod" > "$lib_dir/a_mod.py"
  echo "import a_mod" > "$lib_dir/b_mod.py"

  local payload
  payload='{"stop_hook_active": false}'

  # Override HARNESS_ROOT to our cyclic lib dir parent... but the hook always
  # scans HARNESS_ROOT/hooks/_lib. Instead override via env.
  # We must create hooks/_lib symlink under a temp root.
  local fake_root
  fake_root="$(mktemp -d)"
  mkdir -p "$fake_root/hooks/_lib"
  cp "$lib_dir/"*.py "$fake_root/hooks/_lib/"
  # Also copy arch_fitness*.py so the detector is available
  cp "$BATS_TEST_DIRNAME/../../hooks/_lib/arch_fitness.py" "$fake_root/hooks/_lib/"
  cp "$BATS_TEST_DIRNAME/../../hooks/_lib/arch_fitness_cli.py" "$fake_root/hooks/_lib/"

  run bash -c "CLAUDE_PLUGIN_ROOT='$fake_root' bash '$HOOK_PATH' <<< '$payload'" 2>&1
  [ "$status" -eq 0 ]

  # We need stderr separately
  local stderr_out
  stderr_out="$(bash -c "CLAUDE_PLUGIN_ROOT='$fake_root' CLAUDE_PLUGIN_DATA='$CLAUDE_PLUGIN_DATA' bash '$HOOK_PATH' <<< '$payload'" 2>&1 >/dev/null)"
  [[ "$stderr_out" == *cycle* ]]

  rm -rf "$lib_dir" "$fake_root"
}

# B3 — acyclic lib → status 0 AND JSONL log contains 'clean'
@test "B3: acyclic lib exits 0 and logs clean" {
  local payload
  payload='{"stop_hook_active": false}'
  run bash "$HOOK_PATH" <<< "$payload"
  [ "$status" -eq 0 ]
  # The real _lib is a clean DAG — find the written JSONL
  local jsonl_file
  jsonl_file="$(find "$CLAUDE_PLUGIN_DATA/metrics" -name "arch-fitness.jsonl" 2>/dev/null | head -1)"
  [ -n "$jsonl_file" ]
  grep -q "clean" "$jsonl_file"
}

# B4 — detector crash path → status 0 AND log contains 'SKIPPED' (not 'clean')
# Uses a fake _lib root where arch_fitness_cli.py exits 1 (simulates absent/broken detector)
@test "B4: detector error exits 0 and logs SKIPPED not clean" {
  local payload fake_root
  payload='{"stop_hook_active": false}'
  fake_root="$(mktemp -d)"
  mkdir -p "$fake_root/hooks/_lib"
  cp "$CLAUDE_PLUGIN_ROOT/hooks/_lib/harness-paths.sh" "$fake_root/hooks/_lib/"
  cp "$CLAUDE_PLUGIN_ROOT/hooks/_lib/log.sh" "$fake_root/hooks/_lib/"
  printf '#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n' > "$fake_root/hooks/_lib/arch_fitness_cli.py"

  run bash -c "CLAUDE_PLUGIN_ROOT='$fake_root' CLAUDE_PLUGIN_DATA='$CLAUDE_PLUGIN_DATA' HARNESS_DATA='$CLAUDE_PLUGIN_DATA' CLAUDE_HOOK_PROFILE=standard bash '$HOOK_PATH'" <<< "$payload"
  [ "$status" -eq 0 ]
  local jsonl_file
  jsonl_file="$(find "$CLAUDE_PLUGIN_DATA/metrics" -name "arch-fitness.jsonl" 2>/dev/null | head -1)"
  [ -n "$jsonl_file" ]
  grep -q "SKIPPED" "$jsonl_file"
  ! grep -q '"clean"' "$jsonl_file"
}

# B5 — hook body contains ADVISORY and NOT [ENFORCED] literal
@test "B5: hook header is ADVISORY, not ENFORCED" {
  grep -q "ADVISORY" "$HOOK_PATH"
  ! grep -q "\[ENFORCED\]" "$HOOK_PATH"
}

# B6 — stop_hook_active=true → status 0, short-circuit (no side effects)
@test "B6: stop_hook_active=true exits 0 with no side effects" {
  run bash "$HOOK_PATH" <<< '{"stop_hook_active": true}'
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
  # Must not have written metrics
  [ ! -d "${CLAUDE_PLUGIN_DATA}/metrics" ] || [ -z "$(ls -A "${CLAUDE_PLUGIN_DATA}/metrics" 2>/dev/null)" ]
}

# C1 — registered in hooks.json SubagentStop (mirror test_mutation_score_gate.bats :145)
@test "C1: arch-fitness-gate.sh registered in hooks.json SubagentStop" {
  run python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
hooks_section = data.get("hooks", {})
stop_entries = hooks_section.get("SubagentStop", [])
for entry_group in stop_entries:
    for hook in entry_group.get("hooks", []):
        for arg in hook.get("args", []):
            if "arch-fitness-gate.sh" in arg:
                sys.exit(0)
sys.exit(1)
PYEOF
  [ "$status" -eq 0 ]
}

# C2 — registered in settings.json SubagentStop (mirror test_mutation_score_gate.bats :162)
@test "C2: arch-fitness-gate.sh registered in settings.json SubagentStop" {
  run python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
hooks_section = data.get("hooks", {})
stop_entries = hooks_section.get("SubagentStop", [])
for entry_group in stop_entries:
    for hook in entry_group.get("hooks", []):
        for arg in hook.get("args", []):
            if "arch-fitness-gate.sh" in arg:
                sys.exit(0)
sys.exit(1)
PYEOF
  [ "$status" -eq 0 ]
}

# C3 — hook file is executable
@test "C3: hook is executable" {
  [ -x "$HOOK_PATH" ]
}
