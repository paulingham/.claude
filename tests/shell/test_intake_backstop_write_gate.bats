#!/usr/bin/env bats
# Tests for the Write/Edit/NotebookEdit advisory branch in intake-backstop.sh.
#
# WHY advisory-only test file: all AC1* tests assert exit 0 unconditionally —
# the branch is Tier-0 advisory. AC-T0 sweeps every combination to prove no exit 2
# path exists from the new branch. AC2/AC3 assert hook registration and header text.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
HOOK="$REPO_ROOT/hooks/intake-backstop.sh"
HOOKS_JSON="$REPO_ROOT/hooks/hooks.json"
SETTINGS_JSON="$REPO_ROOT/settings.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a minimal hook stdin JSON for Write/Edit/NotebookEdit.
#   _ibs_json <tool_name> <path_key> <path_value> [session_id]
_ibs_json() {
  local tool="$1" key="$2" path="$3" sid="${4:-test-session-abc}"
  printf '{"tool_name":"%s","session_id":"%s","tool_input":{"%s":"%s"}}' \
    "$tool" "$sid" "$key" "$path"
}

# Make a marker file so the marker short-circuit fires.
#   _make_marker <harness_data_dir> <session_id>
_make_marker() {
  local hd="$1" sid="$2"
  mkdir -p "$hd/intake-markers"
  touch "$hd/intake-markers/$sid.marker"
}

# ---------------------------------------------------------------------------
# AC1a: Write tracked-source, no marker → INTAKE ADVISORY + exit 0
# ---------------------------------------------------------------------------
@test "AC1a: Write to tracked source path, no marker → advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path rules/core.md test-session-ac1a)
  local cwd; cwd=$(mktemp -d)
  # WHY cd to non-repo cwd: prevents git rev-parse from returning the worktree
  # path, which would trigger _ibs_caller_in_worktree and short-circuit the hook.
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  echo "output: $output"
  [[ "$output" == *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC1b: Write WITH marker present → no advisory + exit 0
# ---------------------------------------------------------------------------
@test "AC1b: Write with marker present → no advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local sid="test-session-ac1b"
  _make_marker "$tmpdir" "$sid"
  local json; json=$(_ibs_json Write file_path rules/core.md "$sid")
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  [[ "$output" != *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC1c: Write to pipeline-state/ path, no marker → no advisory (state-safe)
# ---------------------------------------------------------------------------
@test "AC1c: Write to pipeline-state/ path → no advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path pipeline-state/foo/plan.md test-session-ac1c)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  [[ "$output" != *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC1d: Write from worktree (CLAUDE_WORKTREE_PATH set) → no advisory + exit 0
# WHY: the in-worktree short-circuit fires on CLAUDE_WORKTREE_PATH before
# reaching the Write branch; advisory must be suppressed.
# ---------------------------------------------------------------------------
@test "AC1d: Write in-worktree (CLAUDE_WORKTREE_PATH) → no advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path rules/core.md test-session-ac1d)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' CLAUDE_WORKTREE_PATH='$REPO_ROOT/.claude/worktrees/agent-XXXX' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  [[ "$output" != *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC1e: Edit AND NotebookEdit tracked-source, no marker → INTAKE ADVISORY
# CRITICAL: NotebookEdit fixture MUST inject notebook_path, NOT file_path.
# If file_path is injected the hook false-GREENs (falls to silent exit).
# ---------------------------------------------------------------------------
@test "AC1e-Edit: Edit tracked-source, no marker → advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Edit file_path rules/core.md test-session-ac1e-edit)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  echo "output: $output"
  [[ "$output" == *"INTAKE ADVISORY"* ]]
}

@test "AC1e-NotebookEdit: NotebookEdit with notebook_path, no marker → advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  # WHY notebook_path not file_path: NotebookEdit delivers .tool_input.notebook_path.
  # The hook extracts `file_path // notebook_path`; injecting file_path here would
  # bypass the notebook_path code path and false-GREEN.
  local json='{"tool_name":"NotebookEdit","session_id":"test-session-ac1e-nb","tool_input":{"notebook_path":"notebooks/analysis.ipynb"}}'
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  echo "output: $output"
  [[ "$output" == *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC1f: CLAUDE_INTAKE_BACKSTOP=off → no advisory + exit 0
# ---------------------------------------------------------------------------
@test "AC1f: CLAUDE_INTAKE_BACKSTOP=off → silent exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path rules/core.md test-session-ac1f)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' CLAUDE_INTAKE_BACKSTOP=off bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  [[ "$output" != *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC-T0: Write/Edit/NotebookEdit NEVER exit 2 across {marker absent, state, non-state}
# The advisory-only contract: NO path from the Write/Edit/NotebookEdit branch
# should reach _ibs_block (exit 2).
# ---------------------------------------------------------------------------
@test "AC-T0: Write no-marker non-state → exit 0 never exit 2" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path rules/core.md test-session-t0-1)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
}

@test "AC-T0: Write no-marker state-path → exit 0 never exit 2" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Write file_path pipeline-state/x.md test-session-t0-2)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
}

@test "AC-T0: Edit no-marker non-state → exit 0 never exit 2" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json Edit file_path hooks/intake-backstop.sh test-session-t0-3)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
}

@test "AC-T0: NotebookEdit no-marker → exit 0 never exit 2" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json='{"tool_name":"NotebookEdit","session_id":"test-session-t0-4","tool_input":{"notebook_path":"analysis.ipynb"}}'
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# AC2: intake-backstop.sh registered under PreToolUse Write AND Edit in BOTH
#      registries. Also validates both files parse as valid JSON.
# ---------------------------------------------------------------------------
@test "AC2-json: hooks.json parses as valid JSON" {
  python3 -c "import json; json.load(open('$HOOKS_JSON'))"
}

@test "AC2-json: settings.json parses as valid JSON" {
  python3 -c "import json; json.load(open('$SETTINGS_JSON'))"
}

@test "AC2: intake-backstop.sh in PreToolUse Write gate-group in hooks.json" {
  python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
# Gate group: PreToolUse Write block containing orchestrator-discipline.sh
for block in blocks:
    if block.get("matcher") != "Write":
        continue
    names = [h["args"][1] for h in block["hooks"] if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Write gate-group")
sys.exit(1)
PYEOF
}

@test "AC2: intake-backstop.sh in PreToolUse Edit gate-group in hooks.json" {
  python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
for block in blocks:
    if block.get("matcher") != "Edit":
        continue
    names = [h["args"][1] for h in block["hooks"] if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Edit gate-group")
sys.exit(1)
PYEOF
}

@test "AC2: intake-backstop.sh in PreToolUse Write gate-group in settings.json" {
  python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
for block in blocks:
    if block.get("matcher") != "Write":
        continue
    names = [h["args"][1] for h in block["hooks"] if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Write gate-group")
sys.exit(1)
PYEOF
}

@test "AC2: intake-backstop.sh in PreToolUse Edit gate-group in settings.json" {
  python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
for block in blocks:
    if block.get("matcher") != "Edit":
        continue
    names = [h["args"][1] for h in block["hooks"] if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Edit gate-group")
sys.exit(1)
PYEOF
}

# ---------------------------------------------------------------------------
# AC3: hook header contains promotion criterion text
# ---------------------------------------------------------------------------
@test "AC3: intake-backstop.sh header contains '>=10'" {
  grep -q '>=10' "$HOOK"
}

@test "AC3: intake-backstop.sh header contains 'false-positive'" {
  grep -q 'false-positive' "$HOOK"
}

@test "AC3: intake-backstop.sh header contains 'advisory'" {
  grep -q 'advisory' "$HOOK"
}
