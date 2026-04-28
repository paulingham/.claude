#!/usr/bin/env bash
# Tests for bash-write-guard.sh and settings-path-lint.sh.
# These guard against orchestrator bypass paths (Bash subprocess writes,
# hardcoded absolute home paths in settings.json).
#
# Run from ~/.claude/: bash hooks/tests/test-bash-write-guard.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1"
  local expected_exit="$2"
  local actual_exit="$3"
  if [[ "$actual_exit" -eq "$expected_exit" ]]; then
    pass "$name"
  else
    fail "$name" "$expected_exit" "$actual_exit"
  fi
}

echo "=== bash-write-guard + settings-path-lint Test Harness ==="
echo ""

# Hermetic scratch repo + worktree (mirrors orchestrator-discipline tests).
BWG_TMP=$(mktemp -d)
BWG_MAIN="$BWG_TMP/main-repo"
git init -q "$BWG_MAIN" 2>/dev/null
(cd "$BWG_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)
BWG_WT="$BWG_MAIN/.claude/worktrees/agent-testid"
mkdir -p "$BWG_MAIN/.claude/worktrees"
(cd "$BWG_MAIN" && git worktree add -q "$BWG_WT" -b worktree-agent-bwg-testid 2>/dev/null)

# -- bash-write-guard.sh -----------------------------------------------------
echo "-- bash-write-guard.sh --"

run_bwg() {
  # $1 = command string, $2 = pwd
  local cmd="$1"
  local cwd="$2"
  (cd "$cwd" && \
    jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/bash-write-guard.sh" > /dev/null 2>&1)
}

# Non-Bash tool -> allow.
(cd "$BWG_MAIN" && echo '{"tool_name":"Write","tool_input":{"file_path":"x.ts"},"hook_event_name":"PreToolUse"}' \
  | bash "$HOOKS_DIR/bash-write-guard.sh" > /dev/null 2>&1)
run_test "non-Bash tool -> allow (exit 0)" 0 $?

# Empty command -> allow.
run_bwg "" "$BWG_MAIN"
run_test "empty command -> allow (exit 0)" 0 $?

# Orchestrator caller (PWD=main): block patterns.
run_bwg "python3 -c \"open('settings.json','w').write('x')\"" "$BWG_MAIN"
run_test "orchestrator: python open(...,'w') on .json -> block (exit 2)" 2 $?

run_bwg "python3 -c \"open('hooks/foo.sh','w').write('x')\"" "$BWG_MAIN"
run_test "orchestrator: python open(...,'w') on .sh -> block (exit 2)" 2 $?

run_bwg "python3 -c \"open('foo.yaml','a').write('x')\"" "$BWG_MAIN"
run_test "orchestrator: python open(...,'a') on .yaml -> block (exit 2)" 2 $?

run_bwg "sed -i 's/foo/bar/' settings.json" "$BWG_MAIN"
run_test "orchestrator: sed -i on .json -> block (exit 2)" 2 $?

run_bwg "sed --in-place 's/foo/bar/' hooks/x.sh" "$BWG_MAIN"
run_test "orchestrator: sed --in-place on .sh -> block (exit 2)" 2 $?

run_bwg "echo hi > settings.json" "$BWG_MAIN"
run_test "orchestrator: redirect > settings.json -> block (exit 2)" 2 $?

run_bwg "echo hi >> hooks/foo.sh" "$BWG_MAIN"
run_test "orchestrator: redirect >> .sh file -> block (exit 2)" 2 $?

run_bwg "jq '.x = 1' src.json > settings.json" "$BWG_MAIN"
run_test "orchestrator: jq output > settings.json -> block (exit 2)" 2 $?

run_bwg "python3 -c \"import json; json.dump({}, open('settings.json','w'))\"" "$BWG_MAIN"
run_test "orchestrator: json.dump + .json filename -> block (exit 2)" 2 $?

# Orchestrator caller (PWD=main): allow safe commands.
run_bwg "python3 script.py" "$BWG_MAIN"
run_test "orchestrator: python3 script.py (no write pattern) -> allow (exit 0)" 0 $?

run_bwg "ls -la" "$BWG_MAIN"
run_test "orchestrator: ls -la -> allow (exit 0)" 0 $?

run_bwg "cat settings.json" "$BWG_MAIN"
run_test "orchestrator: cat settings.json (read only) -> allow (exit 0)" 0 $?

run_bwg "jq '.x' settings.json > /tmp/out.json" "$BWG_MAIN"
run_test "orchestrator: jq output to /tmp/*.json (not protected) -> allow (exit 0)" 0 $?

run_bwg "echo hi > /tmp/foo.txt" "$BWG_MAIN"
run_test "orchestrator: redirect to /tmp/foo.txt -> allow (exit 0)" 0 $?

run_bwg "sed -i '' 's/foo/bar/' README.md" "$BWG_MAIN"
run_test "orchestrator: sed -i on .md (not protected) -> allow (exit 0)" 0 $?

# Worktree caller -> allow everything (agents are trusted).
run_bwg "python3 -c \"open('settings.json','w').write('x')\"" "$BWG_WT"
run_test "worktree: python open(...,'w') on .json -> allow (exit 0)" 0 $?

run_bwg "sed -i 's/foo/bar/' settings.json" "$BWG_WT"
run_test "worktree: sed -i on .json -> allow (exit 0)" 0 $?

run_bwg "echo hi > hooks/x.sh" "$BWG_WT"
run_test "worktree: redirect > .sh -> allow (exit 0)" 0 $?

echo ""

# -- settings-path-lint.sh ---------------------------------------------------
echo "-- settings-path-lint.sh --"

# Lint targets the REAL ~/.claude/settings.json. Tests assert the live file is
# already clean, then simulate dirty content via a temp file + env override.

run_spl() {
  # $1 = command string, $2 = pwd, $3 = optional override settings file
  # NOTE: var-prefix-then-pipe (`VAR=x cmd1 | cmd2`) only exports VAR to cmd1.
  # Export inside the subshell so both pipe halves see CLAUDE_SETTINGS_FILE.
  local cmd="$1"
  local cwd="$2"
  local override="${3:-}"
  (
    cd "$cwd" || return 1
    [[ -n "$override" ]] && export CLAUDE_SETTINGS_FILE="$override"
    jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/settings-path-lint.sh" > /dev/null 2>&1
  )
}

# Non-Bash -> allow.
(cd "$BWG_MAIN" && echo '{"tool_name":"Write","tool_input":{"file_path":"x"},"hook_event_name":"PreToolUse"}' \
  | bash "$HOOKS_DIR/settings-path-lint.sh" > /dev/null 2>&1)
run_test "non-Bash tool -> allow (exit 0)" 0 $?

# Bash but not git commit/push -> allow.
run_spl "ls -la" "$BWG_MAIN"
run_test "non-commit bash command -> allow (exit 0)" 0 $?

run_spl "git status" "$BWG_MAIN"
run_test "git status (read-only) -> allow (exit 0)" 0 $?

# Set up override settings files for the commit/push checks.
SPL_CLEAN="$BWG_TMP/settings-clean.json"
SPL_DIRTY_USERS="$BWG_TMP/settings-dirty-users.json"
SPL_DIRTY_HOME="$BWG_TMP/settings-dirty-home.json"

cat > "$SPL_CLEAN" <<'EOF'
{
  "mcpServers": {
    "x": {"command": "bash", "args": ["-c", "$HOME/.claude/foo.sh"]}
  }
}
EOF

cat > "$SPL_DIRTY_USERS" <<'EOF'
{
  "mcpServers": {
    "x": {"command": "/Users/Paul.Ingham/.claude/bin/foo", "args": []}
  }
}
EOF

cat > "$SPL_DIRTY_HOME" <<'EOF'
{
  "mcpServers": {
    "x": {"command": "bash", "args": ["/home/runner/.claude/foo.sh"]}
  }
}
EOF

# Clean settings -> allow commit/push.
run_spl "git commit -m 'msg'" "$BWG_MAIN" "$SPL_CLEAN"
run_test "git commit + clean settings -> allow (exit 0)" 0 $?

run_spl "git push origin main" "$BWG_MAIN" "$SPL_CLEAN"
run_test "git push + clean settings -> allow (exit 0)" 0 $?

# Dirty settings (Users) -> block commit.
run_spl "git commit -m 'msg'" "$BWG_MAIN" "$SPL_DIRTY_USERS"
run_test "git commit + /Users/X/.claude/ in args -> block (exit 2)" 2 $?

run_spl "git push origin main" "$BWG_MAIN" "$SPL_DIRTY_USERS"
run_test "git push + /Users/X/.claude/ in args -> block (exit 2)" 2 $?

# Dirty settings (home) -> block commit.
run_spl "git commit -am 'msg'" "$BWG_MAIN" "$SPL_DIRTY_HOME"
run_test "git commit + /home/X/.claude/ in args -> block (exit 2)" 2 $?

# Worktree caller -> always allow (agents trusted).
run_spl "git commit -m 'msg'" "$BWG_WT" "$SPL_DIRTY_USERS"
run_test "worktree: git commit + dirty settings -> allow (exit 0)" 0 $?

# Cleanup
(cd "$BWG_MAIN" && git worktree remove --force "$BWG_WT" 2>/dev/null)
rm -rf "$BWG_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
