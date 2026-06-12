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

@test "AC-T0: MultiEdit no-marker non-state → exit 0 never exit 2" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json MultiEdit file_path hooks/intake-backstop.sh test-session-t0-5)
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

@test "AC2: intake-backstop.sh in PreToolUse Write/Edit gate-group in hooks.json" {
  python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
# Gate group: PreToolUse block whose matcher covers Write and Edit (may be combined)
# and which also contains orchestrator-discipline.sh and intake-backstop.sh.
for block in blocks:
    matcher = block.get("matcher", "")
    if "Write" not in matcher or "Edit" not in matcher:
        continue
    names = [h["args"][1] for h in block.get("hooks", []) if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Write/Edit gate-group")
sys.exit(1)
PYEOF
}

@test "AC2: intake-backstop.sh in PreToolUse Write/Edit gate-group in settings.json" {
  python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])
for block in blocks:
    matcher = block.get("matcher", "")
    if "Write" not in matcher or "Edit" not in matcher:
        continue
    names = [h["args"][1] for h in block.get("hooks", []) if len(h.get("args", [])) > 1]
    if any("orchestrator-discipline" in n for n in names):
        if any("intake-backstop" in n for n in names):
            sys.exit(0)
print("FAIL: intake-backstop.sh not found in PreToolUse Write/Edit gate-group")
sys.exit(1)
PYEOF
}

# ---------------------------------------------------------------------------
# AC1e-MultiEdit: MultiEdit with file_path, no marker → INTAKE ADVISORY
# WHY MultiEdit: MultiEdit is registered as a PreToolUse matcher
# (planning-agent-edit-scope.sh) and uses .tool_input.file_path — same as Edit.
# ---------------------------------------------------------------------------
@test "AC1e-MultiEdit: MultiEdit tracked-source, no marker → advisory + exit 0" {
  local tmpdir; tmpdir=$(mktemp -d)
  local json; json=$(_ibs_json MultiEdit file_path rules/core.md test-session-ac1e-multi)
  local cwd; cwd=$(mktemp -d)
  run bash -c "cd '$cwd' && printf '%s' '$json' | env CLAUDE_PLUGIN_DATA='$tmpdir' CLAUDE_PLUGIN_ROOT='$REPO_ROOT' bash '$HOOK'"
  rm -rf "$tmpdir" "$cwd"
  [ "$status" -eq 0 ]
  echo "output: $output"
  [[ "$output" == *"INTAKE ADVISORY"* ]]
}

# ---------------------------------------------------------------------------
# AC-CC (cross-check): the REGISTERED matcher(s) for intake-backstop in
# BOTH registries must contain NotebookEdit AND MultiEdit.
# WHY: bare Write/Edit matchers don't route NotebookEdit/MultiEdit calls to
# the hook at all — a combined matcher string (e.g. Write|Edit|MultiEdit|NotebookEdit)
# is required, mirroring the shadow-git-checkpoint shape. This test goes RED
# against a bare Write or Edit matcher and GREEN only after the combined matcher
# is wired in.
# ---------------------------------------------------------------------------
@test "AC-CC: hooks.json intake-backstop matcher covers NotebookEdit and MultiEdit" {
  python3 - "$HOOKS_JSON" <<'PYEOF'
import json, sys

data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])

# Find the orchestrator-discipline gate group block that contains intake-backstop.sh.
# WHY orchestrator-discipline: intake-backstop must be routed in the same
# combined matcher as orchestrator-discipline (the Write/Edit gate group).
# The Bash-matcher block also has intake-backstop but is not the target here.
for block in blocks:
    names = [h["args"][1] for h in block.get("hooks", []) if len(h.get("args", [])) > 1]
    if not any("orchestrator-discipline" in n for n in names):
        continue
    if not any("intake-backstop" in n for n in names):
        print("FAIL: orchestrator-discipline gate group does not contain intake-backstop.sh")
        sys.exit(1)
    matcher = block.get("matcher", "")
    has_nb = "NotebookEdit" in matcher
    has_me = "MultiEdit" in matcher
    if has_nb and has_me:
        sys.exit(0)
    missing = []
    if not has_nb:
        missing.append("NotebookEdit")
    if not has_me:
        missing.append("MultiEdit")
    print(f"FAIL: orchestrator-discipline gate group matcher={repr(matcher)} missing: {missing}")
    sys.exit(1)

print("FAIL: no orchestrator-discipline gate group found in PreToolUse hooks.json")
sys.exit(1)
PYEOF
}

@test "AC-CC: settings.json intake-backstop matcher covers NotebookEdit and MultiEdit" {
  python3 - "$SETTINGS_JSON" <<'PYEOF'
import json, sys

data = json.load(open(sys.argv[1]))
blocks = data["hooks"].get("PreToolUse", [])

for block in blocks:
    names = [h["args"][1] for h in block.get("hooks", []) if len(h.get("args", [])) > 1]
    if not any("orchestrator-discipline" in n for n in names):
        continue
    if not any("intake-backstop" in n for n in names):
        print("FAIL: orchestrator-discipline gate group does not contain intake-backstop.sh")
        sys.exit(1)
    matcher = block.get("matcher", "")
    has_nb = "NotebookEdit" in matcher
    has_me = "MultiEdit" in matcher
    if has_nb and has_me:
        sys.exit(0)
    missing = []
    if not has_nb:
        missing.append("NotebookEdit")
    if not has_me:
        missing.append("MultiEdit")
    print(f"FAIL: orchestrator-discipline gate group matcher={repr(matcher)} missing: {missing}")
    sys.exit(1)

print("FAIL: no orchestrator-discipline gate group found in PreToolUse settings.json")
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
