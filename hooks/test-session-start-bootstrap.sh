#!/usr/bin/env bash
# Test script for session-start-bootstrap.sh
# Validates: syntax, output structure, non-git safety, section ordering
#
# enforces: rules/core.md:Iron Laws
# protects: pipeline

HOOK="$HOME/.claude/hooks/session-start-bootstrap.sh"
PASS=0
FAIL=0
TOTAL=0

assert() {
    local description="$1"
    local result="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$result" == "0" ]]; then
        PASS=$((PASS + 1))
        echo "  PASS: $description"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $description"
    fi
}

echo "=== Session Start Bootstrap Hook Tests ==="
echo ""

# --- Test 1: Syntax check ---
echo "--- Syntax ---"
bash -n "$HOOK" 2>/dev/null
assert "Hook passes bash -n syntax check" "$?"

# --- Test 2: Runs without error in a git repo ---
echo "--- Execution (git repo) ---"
OUTPUT=$(cd "$HOME/.claude" && bash "$HOOK" 2>/dev/null)
EXIT_CODE=$?
assert "Hook exits 0 in a git repo directory" "$EXIT_CODE"

# --- Test 3: Runs without error in a non-git directory ---
echo "--- Execution (non-git directory) ---"
OUTPUT_NONGIT=$(cd /tmp && bash "$HOOK" 2>/dev/null)
EXIT_CODE_NONGIT=$?
assert "Hook exits 0 in /tmp (non-git directory)" "$EXIT_CODE_NONGIT"

# --- Test 4: Skill awareness present ---
echo "--- Content: Skill Awareness ---"
echo "$OUTPUT" | grep -q "SKILL AWARENESS BOOTSTRAP:"
assert "Output contains SKILL AWARENESS BOOTSTRAP header" "$?"

# --- Test 5: Iron Laws present ---
echo "--- Content: Iron Laws ---"
echo "$OUTPUT" | grep -q "IRON LAWS:"
assert "Output contains IRON LAWS header" "$?"

# --- Test 6: Iron Laws section comes after Skill Awareness ---
echo "--- Ordering ---"
SKILL_LINE=$(echo "$OUTPUT" | grep -n "SKILL AWARENESS BOOTSTRAP:" | head -1 | cut -d: -f1)
IRON_LINE=$(echo "$OUTPUT" | grep -n "IRON LAWS:" | head -1 | cut -d: -f1)
if [[ -n "$SKILL_LINE" && -n "$IRON_LINE" && "$IRON_LINE" -gt "$SKILL_LINE" ]]; then
    assert "IRON LAWS appears after SKILL AWARENESS" "0"
else
    assert "IRON LAWS appears after SKILL AWARENESS" "1"
fi

# --- Test 7: Pipeline detection section exists in script ---
echo "--- Content: New Sections in Script ---"
grep -q "Pipeline state detection" "$HOOK"
assert "Script contains pipeline state detection section" "$?"

grep -q "Session memory" "$HOOK"
assert "Script contains session memory section" "$?"

grep -q "Stale worktree detection" "$HOOK"
assert "Script contains stale worktree detection section" "$?"

# --- Test 8: New sections appear before IRON LAWS in script ---
echo "--- Ordering: New sections before IRON LAWS in script ---"
PIPELINE_LINE=$(grep -n "Pipeline state detection" "$HOOK" | head -1 | cut -d: -f1)
SESSION_LINE=$(grep -n "Session memory" "$HOOK" | head -1 | cut -d: -f1)
WORKTREE_LINE=$(grep -n "Stale worktree detection" "$HOOK" | head -1 | cut -d: -f1)
IRON_SCRIPT_LINE=$(grep -n "IRON LAWS:" "$HOOK" | head -1 | cut -d: -f1)

if [[ -n "$PIPELINE_LINE" && -n "$IRON_SCRIPT_LINE" && "$PIPELINE_LINE" -lt "$IRON_SCRIPT_LINE" ]]; then
    assert "Pipeline detection section appears before IRON LAWS in script" "0"
else
    assert "Pipeline detection section appears before IRON LAWS in script" "1"
fi

if [[ -n "$SESSION_LINE" && -n "$IRON_SCRIPT_LINE" && "$SESSION_LINE" -lt "$IRON_SCRIPT_LINE" ]]; then
    assert "Session memory section appears before IRON LAWS in script" "0"
else
    assert "Session memory section appears before IRON LAWS in script" "1"
fi

if [[ -n "$WORKTREE_LINE" && -n "$IRON_SCRIPT_LINE" && "$WORKTREE_LINE" -lt "$IRON_SCRIPT_LINE" ]]; then
    assert "Stale worktree section appears before IRON LAWS in script" "0"
else
    assert "Stale worktree section appears before IRON LAWS in script" "1"
fi

# --- Test 9: Ordering of new sections relative to each other ---
if [[ -n "$PIPELINE_LINE" && -n "$SESSION_LINE" && -n "$WORKTREE_LINE" ]]; then
    if [[ "$PIPELINE_LINE" -lt "$SESSION_LINE" && "$SESSION_LINE" -lt "$WORKTREE_LINE" ]]; then
        assert "New sections are in order: pipeline -> session -> worktree" "0"
    else
        assert "New sections are in order: pipeline -> session -> worktree" "1"
    fi
fi

# --- Test 10: Non-git directory does NOT produce worktree/session output ---
echo "--- Safety: Non-git directory ---"
echo "$OUTPUT_NONGIT" | grep -q "STALE WORKTREES"
if [[ $? -ne 0 ]]; then
    assert "Non-git directory does NOT output STALE WORKTREES" "0"
else
    assert "Non-git directory does NOT output STALE WORKTREES" "1"
fi

echo "$OUTPUT_NONGIT" | grep -q "SESSION MEMORY"
if [[ $? -ne 0 ]]; then
    assert "Non-git directory does NOT output SESSION MEMORY (no git remote)" "0"
else
    assert "Non-git directory does NOT output SESSION MEMORY (no git remote)" "1"
fi

# --- Test 11: No background service text in stdout ---
echo "--- Safety: No background noise in stdout ---"
echo "$OUTPUT" | grep -q "supervisor"
if [[ $? -ne 0 ]]; then
    assert "No 'supervisor' text in stdout" "0"
else
    assert "No 'supervisor' text in stdout" "1"
fi

echo "$OUTPUT" | grep -q "nohup"
if [[ $? -ne 0 ]]; then
    assert "No 'nohup' text in stdout" "0"
else
    assert "No 'nohup' text in stdout" "1"
fi

# --- Test 12: Script uses no network calls in new sections ---
echo "--- Safety: No network calls ---"
# Check the new sections (between learning system and IRON LAWS) for network commands
AFTER_LEARNING=$(sed -n '/Pipeline state detection/,/IRON LAWS/p' "$HOOK")
echo "$AFTER_LEARNING" | grep -qE 'curl |wget |gh api|gh pr view'
if [[ $? -ne 0 ]]; then
    assert "No network calls (curl/wget/gh api/gh pr view) in new sections" "0"
else
    assert "No network calls (curl/wget/gh api/gh pr view) in new sections" "1"
fi

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
exit $FAIL
