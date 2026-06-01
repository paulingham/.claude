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

# C5: session-memory-read-split.sh _smr_config_dir uses HARNESS_DATA (Slice 2: further migrated from HARNESS_ROOT)
if grep -q 'HARNESS_DATA' "$REPO_ROOT/hooks/_lib/session-memory-read-split.sh" 2>/dev/null; then
  pass "C5: session-memory-read-split.sh _smr_config_dir references HARNESS_DATA"
else
  fail "C5: session-memory-read-split.sh _smr_config_dir references HARNESS_DATA" "present" "absent"
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
# B6 (Slice 2 Wave A): residual $HOME/.claude/<state-seg> literal count = 0
# Excludes hooks/tests/ and comment lines.
# ---------------------------------------------------------------------------
echo "-- B6: residual state-path literals (Slice 2 Wave A) --"
B6_COUNT=$(python3 - "$REPO_ROOT" <<'PYEOF'
import os, re, sys
pattern = re.compile(r'\$HOME/\.claude/(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|\.hook-self-test-state|plan-cache)')
comment = re.compile(r'^\s*#')
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root + '/hooks'):
    dirs[:] = [x for x in dirs if x != 'tests']
    for f in files:
        if not f.endswith('.sh'):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line) and not comment.match(line):
                    count += 1
print(count)
PYEOF
)
B6_COUNT="${B6_COUNT// /}"
if [[ "$B6_COUNT" -eq 0 ]]; then pass "B6: zero residual \$HOME/.claude/<state-seg> literals in hooks/ (excl tests/, comments)"
else fail "B6: zero residual \$HOME/.claude/<state-seg> literals in hooks/ (excl tests/, comments)" 0 "$B6_COUNT"; fi

# ---------------------------------------------------------------------------
# D4-D6 (Slice 2 Wave A): state-dir / hook-self-test / _smr_config_dir
# ---------------------------------------------------------------------------
echo "-- D4-D6: state-dir, hook-self-test sentinel, _smr_config_dir (Slice 2 Wave A) --"

# D4: _state_dir honours CLAUDE_PLUGIN_DATA
PD4="${TMPDIR:-/tmp}/hp-d4-$$"
mkdir -p "$PD4"
(
  export CLAUDE_PLUGIN_DATA="$PD4"
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR  2>/dev/null || true
  unset CLAUDE_STATE_DIR   2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  source "$REPO_ROOT/hooks/_lib/state-dir.sh"
  result=$(_state_dir)
  [[ "$result" == "${PD4}/state" ]]
)
rc=$?
rm -rf "$PD4"
if [[ $rc -eq 0 ]]; then pass "D4: _state_dir honours CLAUDE_PLUGIN_DATA"
else fail "D4: _state_dir honours CLAUDE_PLUGIN_DATA" "\$CLAUDE_PLUGIN_DATA/state" "(wrong value)"; fi

# D5: hook-self-test.sh SELF_TEST_SENTINEL literal uses $HARNESS_DATA (not $HOME/.claude)
# Verify by inspecting the source text of hook-self-test.sh for the rewritten pattern.
if grep -q 'HARNESS_DATA' "$REPO_ROOT/hooks/hook-self-test.sh" 2>/dev/null \
   && ! grep -E 'SELF_TEST_SENTINEL=.*\$HOME' "$REPO_ROOT/hooks/hook-self-test.sh" 2>/dev/null | grep -qv '^[[:space:]]*#'; then
  pass "D5: hook-self-test sentinel uses HARNESS_DATA (not literal \$HOME/.claude)"
else
  fail "D5: hook-self-test sentinel uses HARNESS_DATA (not literal \$HOME/.claude)" "HARNESS_DATA" "still \$HOME or absent"
fi

# D6: _smr_config_dir == HARNESS_DATA (not HARNESS_ROOT)
PD6_ROOT="${TMPDIR:-/tmp}/hp-d6-root-$$"
PD6_DATA="${TMPDIR:-/tmp}/hp-d6-data-$$"
mkdir -p "$PD6_ROOT" "$PD6_DATA"
(
  export CLAUDE_PLUGIN_ROOT="$PD6_ROOT"
  export CLAUDE_PLUGIN_DATA="$PD6_DATA"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  unset _HARNESS_PATHS_LOADED 2>/dev/null || true
  source "$HARNESS_PATHS"
  # Source the codebase-map-divergence stub (harmless if absent)
  _codebase_map_emit_divergence() { :; }
  _codebase_map_emit_fallback()   { :; }
  source "$REPO_ROOT/hooks/_lib/session-memory-read-split.sh" 2>/dev/null
  result=$(_smr_config_dir)
  [[ "$result" == "$PD6_DATA" ]]
)
rc=$?
rm -rf "$PD6_ROOT" "$PD6_DATA"
if [[ $rc -eq 0 ]]; then pass "D6: _smr_config_dir returns HARNESS_DATA (not HARNESS_ROOT)"
else fail "D6: _smr_config_dir returns HARNESS_DATA (not HARNESS_ROOT)" "\$HARNESS_DATA" "\$HARNESS_ROOT or wrong"; fi

# ---------------------------------------------------------------------------
# E1-E3 (Slice 2 Wave B): Python helper HARNESS_DATA precedence
# Tests intake-fingerprint-emit.py::_is_path_contained root derivation.
# ---------------------------------------------------------------------------
echo "-- E1-E3: Python helper HARNESS_DATA precedence (Slice 2 Wave B) --"

# E1: HARNESS_DATA wins over CLAUDE_CONFIG_DIR
E1_HD="${TMPDIR:-/tmp}/hp-e1-hd-$$"
E1_CCD="${TMPDIR:-/tmp}/hp-e1-ccd-$$"
mkdir -p "$E1_HD" "$E1_CCD"
E1_RESULT=$(HARNESS_DATA="$E1_HD" CLAUDE_CONFIG_DIR="$E1_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__) if False else ".", "hooks/_lib"))
# Replicate the contract: HARNESS_DATA > CLAUDE_CONFIG_DIR > $HOME/.claude
config_dir = (
    os.environ.get("HARNESS_DATA")
    or os.environ.get("CLAUDE_CONFIG_DIR")
    or os.path.join(os.path.expanduser("~"), ".claude")
)
# Test intake-fingerprint-emit.py using same logic
fp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)) if False else "hooks/_lib", "intake-fingerprint-emit.py")
# Read and extract the _is_path_contained function's config_dir derivation
import importlib.util
spec = importlib.util.spec_from_file_location("ifp", "hooks/_lib/intake-fingerprint-emit.py")
mod = importlib.util.module_from_spec(spec)
# Patch os.environ check - the module reads env at call time
spec.loader.exec_module(mod)
# Call _is_path_contained with a path we know is inside HARNESS_DATA/pipeline-state
test_path = os.path.join(os.environ["HARNESS_DATA"], "pipeline-state")
os.makedirs(test_path, exist_ok=True)
result = mod._is_path_contained(test_path)
print("yes" if result else "no")
PYEOF
)
rm -rf "$E1_HD" "$E1_CCD"
if [[ "$E1_RESULT" == "yes" ]]; then pass "E1: Python _is_path_contained uses HARNESS_DATA over CLAUDE_CONFIG_DIR"
else fail "E1: Python _is_path_contained uses HARNESS_DATA over CLAUDE_CONFIG_DIR" "yes" "${E1_RESULT}"; fi

# E2: CLAUDE_CONFIG_DIR used when HARNESS_DATA unset
E2_CCD="${TMPDIR:-/tmp}/hp-e2-ccd-$$"
mkdir -p "$E2_CCD"
E2_RESULT=$(CLAUDE_CONFIG_DIR="$E2_CCD" python3 - <<'PYEOF'
import os
import importlib.util
# Unset HARNESS_DATA for this test
os.environ.pop("HARNESS_DATA", None)
spec = importlib.util.spec_from_file_location("ifp", "hooks/_lib/intake-fingerprint-emit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
test_path = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "pipeline-state")
os.makedirs(test_path, exist_ok=True)
result = mod._is_path_contained(test_path)
print("yes" if result else "no")
PYEOF
)
rm -rf "$E2_CCD"
if [[ "$E2_RESULT" == "yes" ]]; then pass "E2: Python _is_path_contained uses CLAUDE_CONFIG_DIR when HARNESS_DATA unset"
else fail "E2: Python _is_path_contained uses CLAUDE_CONFIG_DIR when HARNESS_DATA unset" "yes" "${E2_RESULT}"; fi

# E3: $HOME/.claude fallback when both unset
E3_RESULT=$(python3 - <<'PYEOF'
import os
import importlib.util
os.environ.pop("HARNESS_DATA", None)
os.environ.pop("CLAUDE_CONFIG_DIR", None)
spec = importlib.util.spec_from_file_location("ifp", "hooks/_lib/intake-fingerprint-emit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
expected_root = os.path.join(os.path.expanduser("~"), ".claude", "pipeline-state")
# We just verify the root is derived correctly by inspecting the path used
# by calling with a canonical path that would be in the default root.
result_in = mod._is_path_contained(expected_root)
print("yes" if result_in else "no")
PYEOF
)
if [[ "$E3_RESULT" == "yes" ]]; then pass "E3: Python _is_path_contained falls back to \$HOME/.claude when both unset"
else fail "E3: Python _is_path_contained falls back to \$HOME/.claude when both unset" "yes" "${E3_RESULT}"; fi

# ---------------------------------------------------------------------------
# F1-F4 (Slice 2 Wave C): gitignore + harness-paths.sh docs
# ---------------------------------------------------------------------------
echo "-- F1-F4: gitignore + harness-paths docs (Slice 2 Wave C) --"

# F1: git ls-files pipeline-state/ | grep -v README is empty
F1_FILES=$(git -C "$REPO_ROOT" ls-files pipeline-state/ 2>/dev/null | grep -v 'README' || true)
F1_COUNT=$(printf '%s' "$F1_FILES" | grep -c '' || echo 0)
F1_COUNT="${F1_COUNT// /}"
# Empty string grep -c returns 0 but printf '' | grep -c '' returns 0 too
if [[ -z "$F1_FILES" ]]; then pass "F1: pipeline-state/ has no git-tracked files except README"
else fail "F1: pipeline-state/ has no git-tracked files except README" 0 "$F1_COUNT"; fi

# F2: pipeline-state/README.md is tracked (if it exists)
F2_TRACKED=$(git -C "$REPO_ROOT" ls-files pipeline-state/README.md 2>/dev/null | wc -l || echo 0)
F2_TRACKED="${F2_TRACKED// /}"
F2_EXISTS=$([ -f "$REPO_ROOT/pipeline-state/README.md" ] && echo 1 || echo 0)
if [[ "$F2_EXISTS" -eq 0 || "$F2_TRACKED" -ge 1 ]]; then pass "F2: pipeline-state/README.md tracked (or absent)"
else fail "F2: pipeline-state/README.md tracked (or absent)" "tracked or absent" "present but untracked"; fi

# F3: session-memory/config and session-memory/adapters are tracked
F3_COUNT=$(git -C "$REPO_ROOT" ls-files session-memory/config/ session-memory/adapters/ 2>/dev/null | wc -l || echo 0)
F3_COUNT="${F3_COUNT// /}"
if [[ "$F3_COUNT" -ge 1 ]]; then pass "F3: session-memory config/adapters are git-tracked"
else fail "F3: session-memory config/adapters are git-tracked" ">=1 files" "0 files"; fi

# F4: harness-paths.sh contains documentation about absolute paths / no trailing slash
if grep -q 'absolute' "$REPO_ROOT/hooks/_lib/harness-paths.sh" 2>/dev/null \
   && grep -q 'trailing' "$REPO_ROOT/hooks/_lib/harness-paths.sh" 2>/dev/null; then
  pass "F4: harness-paths.sh contains absolute-path / no-trailing-slash docs"
else
  fail "F4: harness-paths.sh contains absolute-path / no-trailing-slash docs" "present" "absent"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
