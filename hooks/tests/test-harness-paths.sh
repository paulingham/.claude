#!/usr/bin/env bash
# Test suite for hooks/_lib/harness-paths.sh
# Run from repo root: bash hooks/tests/test-harness-paths.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HARNESS_PATHS="$REPO_ROOT/hooks/_lib/harness-paths.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

# ---------------------------------------------------------------------------
# A-series: variable resolution
# ---------------------------------------------------------------------------
echo "-- harness-paths.sh variable resolution --"

# A1: unset → HARNESS_ROOT == $HOME/.claude
(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "$HOME/.claude" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A1: unset vars → HARNESS_ROOT == \$HOME/.claude"
else fail "A1: unset vars → HARNESS_ROOT == \$HOME/.claude" "$HOME/.claude" "(not matched)"; fi

# A2: CLAUDE_PLUGIN_ROOT wins over CLAUDE_CONFIG_DIR
(
  export CLAUDE_PLUGIN_ROOT="/tmp/plugin-root-test"
  export CLAUDE_CONFIG_DIR="/tmp/config-dir-test"
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "/tmp/plugin-root-test" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A2: CLAUDE_PLUGIN_ROOT wins over CLAUDE_CONFIG_DIR"
else fail "A2: CLAUDE_PLUGIN_ROOT wins over CLAUDE_CONFIG_DIR" "/tmp/plugin-root-test" "(wrong value)"; fi

# A3: CLAUDE_CONFIG_DIR beats $HOME/.claude when PLUGIN_ROOT unset
(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  export CLAUDE_CONFIG_DIR="/tmp/config-dir-only"
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "/tmp/config-dir-only" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A3: CLAUDE_CONFIG_DIR beats \$HOME/.claude when PLUGIN_ROOT unset"
else fail "A3: CLAUDE_CONFIG_DIR beats \$HOME/.claude when PLUGIN_ROOT unset" "/tmp/config-dir-only" "(wrong value)"; fi

# A4: HARNESS_DATA uses CLAUDE_PLUGIN_DATA
(
  export CLAUDE_PLUGIN_DATA="/tmp/plugin-data-test"
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_DATA" == "/tmp/plugin-data-test" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A4: HARNESS_DATA uses CLAUDE_PLUGIN_DATA"
else fail "A4: HARNESS_DATA uses CLAUDE_PLUGIN_DATA" "/tmp/plugin-data-test" "(wrong value)"; fi

# A5: data fallback identical to HARNESS_ROOT when neither plugin var set
(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_DATA" == "$HARNESS_ROOT" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A5: data fallback identical to HARNESS_ROOT when no plugin vars"
else fail "A5: data fallback identical to HARNESS_ROOT when no plugin vars" "same as HARNESS_ROOT" "different"; fi

# A6: source-guard idempotent — double-source is a no-op
(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  first="$HARNESS_ROOT"
  # Now set a different env and source again — guard must suppress second load
  export CLAUDE_PLUGIN_ROOT="/tmp/should-not-override"
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "$first" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A6: source-guard idempotent (double-source no-op)"
else fail "A6: source-guard idempotent (double-source no-op)" "unchanged after re-source" "value changed"; fi

# A6b: safe under set -u (no unbound variable errors)
(
  set -u
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A6b: safe under set -u (no unbound variable errors)"
else fail "A6b: safe under set -u (no unbound variable errors)" 0 $rc; fi

# A7: CLAUDE_PLUGIN_ROOT="" (empty string) falls back to $HOME/.claude
# The ${VAR:-default} form treats empty string identically to unset.
(
  export CLAUDE_PLUGIN_ROOT=""
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "$HOME/.claude" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "A7: CLAUDE_PLUGIN_ROOT=\"\" (empty) falls back to \$HOME/.claude"
else fail "A7: CLAUDE_PLUGIN_ROOT=\"\" (empty) falls back to \$HOME/.claude" "$HOME/.claude" "(wrong value)"; fi

# ---------------------------------------------------------------------------
# B-series: residual pattern assertions
# Note: hooks/tests/ is excluded from the glob below because this test file
# itself contains the old ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib
# pattern as literal strings in the grep -rl search targets. Scanning it
# would produce false positives against the test's own source text.
# ---------------------------------------------------------------------------
echo "-- residual pattern assertions --"

# B1: zero residual ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib in any .sh
count=$(grep -rl '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib' \
  "$REPO_ROOT/hooks/"*.sh "$REPO_ROOT/hooks/_lib/"*.sh 2>/dev/null | wc -l)
count="${count// /}"
if [[ "$count" -eq 0 ]]; then pass "B1: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/_lib in .sh files"
else fail "B1: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/_lib in .sh files" 0 "$count"; fi

# B2: zero residual ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh form
count=$(grep -rl '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh' \
  "$REPO_ROOT/hooks/"*.sh "$REPO_ROOT/hooks/_lib/"*.sh 2>/dev/null | wc -l)
count="${count// /}"
if [[ "$count" -eq 0 ]]; then pass "B2: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/hook-profile.sh in .sh files"
else fail "B2: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/hook-profile.sh in .sh files" 0 "$count"; fi

# B3: zero residual ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh form
count=$(grep -rl '${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh' \
  "$REPO_ROOT/hooks/"*.sh "$REPO_ROOT/hooks/_lib/"*.sh 2>/dev/null | wc -l)
count="${count// /}"
if [[ "$count" -eq 0 ]]; then pass "B3: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/loop-guard.sh in .sh files"
else fail "B3: zero residual \${CLAUDE_CONFIG_DIR:-\$HOME/.claude}/hooks/loop-guard.sh in .sh files" 0 "$count"; fi

# B4: bash -n clean on harness-paths.sh
bash -n "$HARNESS_PATHS" 2>/dev/null
rc=$?
if [[ $rc -eq 0 ]]; then pass "B4: bash -n clean on harness-paths.sh"
else fail "B4: bash -n clean on harness-paths.sh" 0 $rc; fi

# B5: bash -n clean on all modified hooks/_lib files listed in plan step 3
for f in \
  hooks/hook-self-test.sh \
  hooks/_lib/harness-audit-fast.sh \
  hooks/_lib/verdict-consistency-check.sh \
  hooks/intake-fingerprint-audit.sh \
  hooks/_lib/session-start-version-check.sh \
  hooks/_lib/session-memory-read-split.sh \
  hooks/_lib/spec-blind-recursion.sh; do
  bash -n "$REPO_ROOT/$f" 2>/dev/null
  rc=$?
  if [[ $rc -eq 0 ]]; then pass "B5: bash -n clean on $f"
  else fail "B5: bash -n clean on $f" 0 $rc; fi
done

# ---------------------------------------------------------------------------
# C-series: post-source refs resolve under a set CLAUDE_PLUGIN_ROOT
# ---------------------------------------------------------------------------
echo "-- C-series: harness-audit-fast.sh uses HARNESS_ROOT --"

# C1: harness-audit-fast.sh references HARNESS_ROOT (not CLAUDE_CONFIG_DIR)
if grep -q 'HARNESS_ROOT' "$REPO_ROOT/hooks/_lib/harness-audit-fast.sh" 2>/dev/null; then
  pass "C1: harness-audit-fast.sh references HARNESS_ROOT"
else
  fail "C1: harness-audit-fast.sh references HARNESS_ROOT" "present" "absent"
fi

# C2: verdict-consistency-check.sh uses HARNESS_ROOT
if grep -q 'HARNESS_ROOT' "$REPO_ROOT/hooks/_lib/verdict-consistency-check.sh" 2>/dev/null; then
  pass "C2: verdict-consistency-check.sh references HARNESS_ROOT"
else
  fail "C2: verdict-consistency-check.sh references HARNESS_ROOT" "present" "absent"
fi

# C3: session-start-version-check.sh uses HARNESS_ROOT
if grep -q 'HARNESS_ROOT' "$REPO_ROOT/hooks/_lib/session-start-version-check.sh" 2>/dev/null; then
  pass "C3: session-start-version-check.sh references HARNESS_ROOT"
else
  fail "C3: session-start-version-check.sh references HARNESS_ROOT" "present" "absent"
fi

# C4: spec-blind-recursion.sh uses HARNESS_ROOT
if grep -q 'HARNESS_ROOT' "$REPO_ROOT/hooks/_lib/spec-blind-recursion.sh" 2>/dev/null; then
  pass "C4: spec-blind-recursion.sh references HARNESS_ROOT"
else
  fail "C4: spec-blind-recursion.sh references HARNESS_ROOT" "present" "absent"
fi

# C5: session-memory-read-split.sh uses HARNESS_ROOT (migrated from CLAUDE_CONFIG_DIR)
if grep -q 'HARNESS_ROOT' "$REPO_ROOT/hooks/_lib/session-memory-read-split.sh" 2>/dev/null; then
  pass "C5: session-memory-read-split.sh references HARNESS_ROOT"
else
  fail "C5: session-memory-read-split.sh references HARNESS_ROOT" "present" "absent"
fi

# ---------------------------------------------------------------------------
# D-series: plug-in mode smoke tests
# ---------------------------------------------------------------------------
echo "-- D-series: plugin-mode variable resolution --"

# D1: CLAUDE_PLUGIN_ROOT set → HARNESS_ROOT picks it up
(
  export CLAUDE_PLUGIN_ROOT="/tmp/plugin-smoke-d1"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "/tmp/plugin-smoke-d1" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "D1: CLAUDE_PLUGIN_ROOT set → HARNESS_ROOT resolves correctly"
else fail "D1: CLAUDE_PLUGIN_ROOT set → HARNESS_ROOT resolves correctly" "/tmp/plugin-smoke-d1" "(wrong)"; fi

# D2: CLAUDE_PLUGIN_DATA set independently of CLAUDE_PLUGIN_ROOT
(
  export CLAUDE_PLUGIN_ROOT="/tmp/plugin-code-d2"
  export CLAUDE_PLUGIN_DATA="/tmp/plugin-data-d2"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "/tmp/plugin-code-d2" && "$HARNESS_DATA" == "/tmp/plugin-data-d2" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "D2: PLUGIN_ROOT and PLUGIN_DATA set independently"
else fail "D2: PLUGIN_ROOT and PLUGIN_DATA set independently" "both correct" "mismatch"; fi

# D3: CLAUDE_CONFIG_DIR fallback when only CONFIG_DIR is set
(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_PLUGIN_DATA 2>/dev/null || true
  export CLAUDE_CONFIG_DIR="/tmp/config-only-d3"
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  [[ "$HARNESS_ROOT" == "/tmp/config-only-d3" && "$HARNESS_DATA" == "/tmp/config-only-d3" ]]
)
rc=$?
if [[ $rc -eq 0 ]]; then pass "D3: CLAUDE_CONFIG_DIR fallback (PLUGIN_ROOT unset)"
else fail "D3: CLAUDE_CONFIG_DIR fallback (PLUGIN_ROOT unset)" "both /tmp/config-only-d3" "mismatch"; fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
