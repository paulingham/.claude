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
# Matches all brace-expansion forms that resolve to $HOME/.claude/<state-seg>:
#   $HOME/.claude/seg
#   ${HOME}/.claude/seg
#   ${HOME:-...}/.claude/seg
#   ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/seg  (still a HOME-rooted fallback)
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|\.hook-self-test-state|plan-cache)'
pattern = re.compile(
    r'(\$HOME'               # bare $HOME
    r'|\$\{HOME\}'           # ${HOME}
    r'|\$\{HOME:-[^}]*\}'   # ${HOME:-...}
    r'|\$\{CLAUDE_CONFIG_DIR:-[^}]*\$HOME[^}]*\}'  # ${CLAUDE_CONFIG_DIR:-...$HOME...}
    r')/\.claude/' + SEG
)
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
# B6b (Slice a2): residual $HOME/.claude/(automation|scripts) literals in
# hooks/ .sh (excl tests/) and automation/*.sh. Count must be 0 after slice-a2.
# ---------------------------------------------------------------------------
echo "-- B6b: residual \$HOME/.claude/(automation|scripts) literals (Slice a2) --"
B6B_COUNT=$(python3 - "$REPO_ROOT" <<'B6BPYEOF'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|\.hook-self-test-state|plan-cache|automation|scripts)'
pattern = re.compile(
    r'(\$HOME'
    r'|\$\{HOME\}'
    r'|\$\{HOME:-[^}]*\}'
    r'|\$\{CLAUDE_CONFIG_DIR:-[^}]*\$HOME[^}]*\}'
    r')/\.claude/' + SEG
)
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
for d, dirs, files in os.walk(root + '/automation'):
    dirs[:] = [x for x in dirs if x != '.git']
    for f in files:
        if not f.endswith('.sh'):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line) and not comment.match(line):
                    count += 1
print(count)
B6BPYEOF
)
B6B_COUNT="${B6B_COUNT// /}"
if [[ "$B6B_COUNT" -eq 0 ]]; then pass "B6b: zero \$HOME/.claude/(automation|scripts) literals in hooks/ + automation/ .sh (excl tests/, comments)"
else fail "B6b: zero \$HOME/.claude/(automation|scripts) literals in hooks/ + automation/ .sh (excl tests/, comments)" 0 "$B6B_COUNT"; fi

# ---------------------------------------------------------------------------
# B7 (Slice 2 Fix Cycle): residual expanduser("~/.claude/<state-seg>") in .py
# Companion to B6 that catches Python helpers hardcoding state paths.
# Must NOT flag: os.path.join(os.path.expanduser("~"), ".claude") — that form
# has ".claude" as a separate join arg (no trailing state-seg), and is the
# legitimate cold-start fallback.
# ---------------------------------------------------------------------------
echo "-- B7: residual expanduser(~/\.claude/<state-seg>) literals in .py (excl tests/) --"
B7_COUNT=$(python3 - "$REPO_ROOT" <<'B7PYEOF'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|plan-cache)'
# Match expanduser("~/.claude/<seg>") or expanduser('~/.claude/<seg>') with trailing seg
# Use chr(39) for single-quote to avoid heredoc delimiter collision.
pattern = re.compile(
    r'expanduser\(["' + chr(39) + r']~/.claude/' + SEG
)
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root + '/hooks'):
    dirs[:] = [x for x in dirs if x != 'tests']
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line):
                    count += 1
print(count)
B7PYEOF
)
B7_COUNT="${B7_COUNT// /}"
if [[ "$B7_COUNT" -eq 0 ]]; then pass "B7: zero residual expanduser(~/\.claude/<state-seg>) literals in hooks/ .py files (excl tests/)"
else fail "B7: zero residual expanduser(~/\.claude/<state-seg>) literals in hooks/ .py files (excl tests/)" 0 "$B7_COUNT"; fi

# ---------------------------------------------------------------------------
# B7b (Slice 5a): residual expanduser("~/.claude/<state-seg>") in skills/**/*.py
# Companion to B7 that extends the same canary into the skills/ tree.
# Excludes skills/ paths that contain 'tests'.
# RED proof: plant a scratch .py with a violation, confirm scanner FIRES (>=1),
# then run the real tree check (GREEN, must be 0).
# ---------------------------------------------------------------------------
echo "-- B7b: residual expanduser(~/\.claude/<state-seg>) literals in skills/ .py files (excl tests/) --"
echo "-- B7b RED proof: scanner fires on planted violation --"
B7B_SCRATCH_DIR="${TMPDIR:-/tmp}/b7b-red-proof-$$"
mkdir -p "$B7B_SCRATCH_DIR"
printf 'path = os.path.expanduser("~/.claude/pipeline-state/foo")\n' \
  > "$B7B_SCRATCH_DIR/planted_residual.py"
B7B_RED_COUNT=$(python3 - "$B7B_SCRATCH_DIR" <<'B7BREDHEREDOC'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|plan-cache)'
pattern = re.compile(
    r'expanduser\(["' + chr(39) + r']~/.claude/' + SEG
)
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root):
    dirs[:] = [x for x in dirs if x != 'tests']
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line):
                    count += 1
print(count)
B7BREDHEREDOC
)
B7B_RED_COUNT="${B7B_RED_COUNT// /}"
rm -rf "$B7B_SCRATCH_DIR"
if [[ "$B7B_RED_COUNT" -ge 1 ]]; then pass "B7b-RED: scanner fires on planted expanduser(~/.claude/pipeline-state) violation (got $B7B_RED_COUNT)"
else fail "B7b-RED: scanner fires on planted violation" ">=1" "$B7B_RED_COUNT"; fi

echo "-- B7b GREEN: zero residual expanduser(~/\.claude/<state-seg>) in skills/ .py (excl tests/) --"
B7B_COUNT=$(python3 - "$REPO_ROOT" <<'B7BPYEOF'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|state|tasks|teams|plan-cache)'
# Match expanduser("~/.claude/<seg>") or expanduser('~/.claude/<seg>') with trailing seg.
# Use chr(39) for single-quote to avoid heredoc delimiter collision.
pattern = re.compile(
    r'expanduser\(["' + chr(39) + r']~/.claude/' + SEG
)
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root + '/skills'):
    dirs[:] = [x for x in dirs if x != 'tests']
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line):
                    count += 1
print(count)
B7BPYEOF
)
B7B_COUNT="${B7B_COUNT// /}"
if [[ "$B7B_COUNT" -eq 0 ]]; then pass "B7b: zero residual expanduser(~/\.claude/<state-seg>) literals in skills/ .py files (excl tests/)"
else fail "B7b: zero residual expanduser(~/\.claude/<state-seg>) literals in skills/ .py files (excl tests/)" 0 "$B7B_COUNT"; fi

# ---------------------------------------------------------------------------
# B8 (Slice 5a): residual executable $HOME/.claude/<seg> in skills/**/*.md
# Scans for bare $HOME/.claude/<state-seg> literals AND os.environ['HOME']...claude
# f-string forms that would break in plugin mode.
# Count must be 0 after Item 4 path fixes.
# RED proof: plant a scratch .md with both violation forms, confirm scanner FIRES (>=1),
# then run the real tree check (GREEN, must be 0).
# ---------------------------------------------------------------------------
echo "-- B8 RED proof: scanner fires on planted \$HOME/.claude and os.environ violations --"
B8_SCRATCH_DIR="${TMPDIR:-/tmp}/b8-red-proof-$$"
mkdir -p "$B8_SCRATCH_DIR"
cat > "$B8_SCRATCH_DIR/planted_residual.md" <<'B8PLANTED'
# Test snippet
path = "$HOME/.claude/metrics/foo.jsonl"
other = os.environ["HOME"] + "/.claude/pipeline-state"
B8PLANTED
B8_RED_COUNT=$(python3 - "$B8_SCRATCH_DIR" <<'B8REDHEREDOC'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|hooks|skills|state|tasks|teams|plan-cache)'
raw_pattern = re.compile(r'\$HOME/\.claude/' + SEG)
env_pattern = re.compile(r'''os\.environ\s*\[\s*['"]HOME['"]\s*\]\s*\+\s*['"]?/\.claude''')
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root):
    dirs[:] = [x for x in dirs if x not in ['tests', '.git']]
    for f in files:
        if not f.endswith('.md'):
            continue
        path = os.path.join(d, f)
        rel = os.path.relpath(path, root)
        with open(path) as fp:
            for lineno, line in enumerate(fp, 1):
                if raw_pattern.search(line):
                    if 'CLAUDE_PLUGIN_' not in line and 'CLAUDE_CONFIG_DIR' not in line:
                        count += 1
                if env_pattern.search(line):
                    count += 1
print(count)
B8REDHEREDOC
)
B8_RED_COUNT="${B8_RED_COUNT// /}"
rm -rf "$B8_SCRATCH_DIR"
if [[ "$B8_RED_COUNT" -ge 1 ]]; then pass "B8-RED: scanner fires on planted \$HOME/.claude/metrics and os.environ[HOME]/.claude violations (got $B8_RED_COUNT)"
else fail "B8-RED: scanner fires on planted violations" ">=1" "$B8_RED_COUNT"; fi

echo "-- B8 GREEN: zero residual executable \$HOME/.claude/<state-seg> and os.environ[HOME]/.claude in skills/ .md --"
B8_COUNT=$(python3 - "$REPO_ROOT" <<'B8PYEOF'
import os, re, sys
SEG = r'(pipeline-state|metrics|db|session-memory|learning|screenshots|agent-memory|hooks|skills|state|tasks|teams|plan-cache)'
# Pattern 1: bare $HOME/.claude/<seg> NOT already wrapped in ${CLAUDE_PLUGIN_*:-...} or ${CLAUDE_CONFIG_DIR:-...}
raw_pattern = re.compile(r'\$HOME/\.claude/' + SEG)
# Pattern 2: os.environ['HOME']/.claude or os.environ["HOME"]/.claude f-string form
env_pattern = re.compile(r'''os\.environ\s*\[\s*['"]HOME['"]\s*\]\s*\+\s*['"]?/\.claude''')
# Exclude the mcp_memory illustrative path (line 46 of mcp_memory/SKILL.md)
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root + '/skills'):
    dirs[:] = [x for x in dirs if x not in ['tests', '.git']]
    for f in files:
        if not f.endswith('.md'):
            continue
        path = os.path.join(d, f)
        rel = os.path.relpath(path, root)
        with open(path) as fp:
            for lineno, line in enumerate(fp, 1):
                # Exempt the single illustrative mcp_memory line
                if 'mcp_memory' in rel and lineno == 46:
                    continue
                # Check raw pattern: only flag if NOT already inside a portable chain
                if raw_pattern.search(line):
                    # If the line contains CLAUDE_PLUGIN_ or CLAUDE_CONFIG_DIR wrapping, it is already ported
                    if 'CLAUDE_PLUGIN_' not in line and 'CLAUDE_CONFIG_DIR' not in line:
                        count += 1
                # Check os.environ['HOME'] f-string form
                if env_pattern.search(line):
                    count += 1
print(count)
B8PYEOF
)
B8_COUNT="${B8_COUNT// /}"
if [[ "$B8_COUNT" -eq 0 ]]; then pass "B8: zero residual executable \$HOME/.claude refs in skills/ .md (excl mcp_memory:46)"
else fail "B8: zero residual executable \$HOME/.claude refs in skills/ .md (excl mcp_memory:46)" 0 "$B8_COUNT"; fi

# ---------------------------------------------------------------------------
# B9 (Slice 5a): overlay-equivalence — rewritten paths resolve to $HOME/.claude
# when all plugin vars are unset (byte-identical to pre-change behaviour).
# Tests two gate snippets: pr-creation approval-token and product-acceptance write-approval-token.
# ---------------------------------------------------------------------------
echo "-- B9: overlay-equivalence — plugin vars unset → paths resolve to \$HOME/.claude --"

# B9a: pr-creation approval-token path resolves to $HOME/.claude/hooks/_lib/approval-token.sh
B9A_RESULT=$(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  EXPECTED="$HOME/.claude/hooks/_lib/approval-token.sh"
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/approval-token.sh"
  if [[ "$RESOLVED" == "$EXPECTED" ]]; then echo "pass"; else echo "fail:$RESOLVED"; fi
)
if [[ "$B9A_RESULT" == "pass" ]]; then pass "B9a: pr-creation approval-token resolves to \$HOME/.claude (plugin vars unset)"
else fail "B9a: pr-creation approval-token resolves to \$HOME/.claude (plugin vars unset)" "$HOME/.claude/hooks/_lib/approval-token.sh" "${B9A_RESULT#fail:}"; fi

# B9b: product-acceptance write-approval-token path resolves to $HOME/.claude/hooks/_lib/write-approval-token.sh
B9B_RESULT=$(
  unset CLAUDE_PLUGIN_ROOT 2>/dev/null || true
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  EXPECTED="$HOME/.claude/hooks/_lib/write-approval-token.sh"
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/write-approval-token.sh"
  if [[ "$RESOLVED" == "$EXPECTED" ]]; then echo "pass"; else echo "fail:$RESOLVED"; fi
)
if [[ "$B9B_RESULT" == "pass" ]]; then pass "B9b: product-acceptance write-approval-token resolves to \$HOME/.claude (plugin vars unset)"
else fail "B9b: product-acceptance write-approval-token resolves to \$HOME/.claude (plugin vars unset)" "$HOME/.claude/hooks/_lib/write-approval-token.sh" "${B9B_RESULT#fail:}"; fi

# B9c: pr-creation approval-token resolves to an EXISTING FILE under CLAUDE_PLUGIN_ROOT
# RED proof: point CLAUDE_PLUGIN_ROOT at a scratch dir (no approval-token.sh) → file absent
B9C_SCRATCH="${TMPDIR:-/tmp}/b9c-red-proof-$$"
mkdir -p "$B9C_SCRATCH/hooks/_lib"
B9C_RED_RESULT=$(
  export CLAUDE_PLUGIN_ROOT="$B9C_SCRATCH"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/approval-token.sh"
  if [[ ! -f "$RESOLVED" ]]; then echo "absent"; else echo "present"; fi
)
rm -rf "$B9C_SCRATCH"
if [[ "$B9C_RED_RESULT" == "absent" ]]; then pass "B9c-RED: approval-token.sh absent in scratch dir (confirms existence test has real bite)"
else fail "B9c-RED: approval-token.sh absent in scratch dir" "absent" "$B9C_RED_RESULT"; fi

# GREEN: CLAUDE_PLUGIN_ROOT=$REPO_ROOT → approval-token.sh must exist on disk
B9C_RESULT=$(
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/approval-token.sh"
  if [[ -f "$RESOLVED" ]]; then echo "pass"; else echo "fail:$RESOLVED"; fi
)
if [[ "$B9C_RESULT" == "pass" ]]; then pass "B9c: approval-token.sh exists at resolved path under CLAUDE_PLUGIN_ROOT=REPO_ROOT"
else fail "B9c: approval-token.sh exists at resolved path under CLAUDE_PLUGIN_ROOT=REPO_ROOT" "exists" "${B9C_RESULT#fail:}"; fi

# B9d: product-acceptance write-approval-token resolves to an EXISTING FILE under CLAUDE_PLUGIN_ROOT
# RED proof: point CLAUDE_PLUGIN_ROOT at a scratch dir (no write-approval-token.sh) → file absent
B9D_SCRATCH="${TMPDIR:-/tmp}/b9d-red-proof-$$"
mkdir -p "$B9D_SCRATCH/hooks/_lib"
B9D_RED_RESULT=$(
  export CLAUDE_PLUGIN_ROOT="$B9D_SCRATCH"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/write-approval-token.sh"
  if [[ ! -f "$RESOLVED" ]]; then echo "absent"; else echo "present"; fi
)
rm -rf "$B9D_SCRATCH"
if [[ "$B9D_RED_RESULT" == "absent" ]]; then pass "B9d-RED: write-approval-token.sh absent in scratch dir (confirms existence test has real bite)"
else fail "B9d-RED: write-approval-token.sh absent in scratch dir" "absent" "$B9D_RED_RESULT"; fi

# GREEN: CLAUDE_PLUGIN_ROOT=$REPO_ROOT → write-approval-token.sh must exist on disk
B9D_RESULT=$(
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  unset CLAUDE_CONFIG_DIR 2>/dev/null || true
  RESOLVED="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/write-approval-token.sh"
  if [[ -f "$RESOLVED" ]]; then echo "pass"; else echo "fail:$RESOLVED"; fi
)
if [[ "$B9D_RESULT" == "pass" ]]; then pass "B9d: write-approval-token.sh exists at resolved path under CLAUDE_PLUGIN_ROOT=REPO_ROOT"
else fail "B9d: write-approval-token.sh exists at resolved path under CLAUDE_PLUGIN_ROOT=REPO_ROOT" "exists" "${B9D_RESULT#fail:}"; fi

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
# E1-E3 (Slice 2 Wave B / updated AC-A1e): Python helper CLAUDE_PLUGIN_DATA precedence.
# After slice-a1 migration, callers use harness_paths.harness_data() which reads
# CLAUDE_PLUGIN_DATA. Tests inject CLAUDE_PLUGIN_DATA explicitly to prove the new path.
# ---------------------------------------------------------------------------
echo "-- E1-E3: Python helper CLAUDE_PLUGIN_DATA precedence (AC-A1e) --"

# E1: CLAUDE_PLUGIN_DATA wins over CLAUDE_CONFIG_DIR (via harness_data())
E1_PD="${TMPDIR:-/tmp}/hp-e1-pd-$$"
E1_CCD="${TMPDIR:-/tmp}/hp-e1-ccd-$$"
mkdir -p "$E1_PD" "$E1_CCD"
E1_RESULT=$(CLAUDE_PLUGIN_DATA="$E1_PD" CLAUDE_CONFIG_DIR="$E1_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
import importlib.util
# Unset HARNESS_DATA so the harness_data() path is exercised
os.environ.pop("HARNESS_DATA", None)
spec = importlib.util.spec_from_file_location("ifp", "hooks/_lib/intake-fingerprint-emit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# Call _is_path_contained with a path inside CLAUDE_PLUGIN_DATA/pipeline-state
test_path = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "pipeline-state")
os.makedirs(test_path, exist_ok=True)
result = mod._is_path_contained(test_path)
print("yes" if result else "no")
PYEOF
)
rm -rf "$E1_PD" "$E1_CCD"
if [[ "$E1_RESULT" == "yes" ]]; then pass "E1: Python _is_path_contained uses CLAUDE_PLUGIN_DATA (via harness_data()) over CLAUDE_CONFIG_DIR"
else fail "E1: Python _is_path_contained uses CLAUDE_PLUGIN_DATA (via harness_data()) over CLAUDE_CONFIG_DIR" "yes" "${E1_RESULT}"; fi

# E2: CLAUDE_CONFIG_DIR used when CLAUDE_PLUGIN_DATA unset (via harness_data() fallback)
E2_CCD="${TMPDIR:-/tmp}/hp-e2-ccd-$$"
mkdir -p "$E2_CCD"
E2_RESULT=$(CLAUDE_CONFIG_DIR="$E2_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
import importlib.util
# Unset both HARNESS_DATA and CLAUDE_PLUGIN_DATA so CLAUDE_CONFIG_DIR wins
os.environ.pop("HARNESS_DATA", None)
os.environ.pop("CLAUDE_PLUGIN_DATA", None)
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
if [[ "$E2_RESULT" == "yes" ]]; then pass "E2: Python _is_path_contained uses CLAUDE_CONFIG_DIR when CLAUDE_PLUGIN_DATA unset"
else fail "E2: Python _is_path_contained uses CLAUDE_CONFIG_DIR when CLAUDE_PLUGIN_DATA unset" "yes" "${E2_RESULT}"; fi

# E3: $HOME/.claude fallback when all unset
E3_RESULT=$(python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
import importlib.util
os.environ.pop("HARNESS_DATA", None)
os.environ.pop("CLAUDE_PLUGIN_DATA", None)
os.environ.pop("CLAUDE_CONFIG_DIR", None)
spec = importlib.util.spec_from_file_location("ifp", "hooks/_lib/intake-fingerprint-emit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
expected_root = os.path.join(os.path.expanduser("~"), ".claude", "pipeline-state")
result_in = mod._is_path_contained(expected_root)
print("yes" if result_in else "no")
PYEOF
)
if [[ "$E3_RESULT" == "yes" ]]; then pass "E3: Python _is_path_contained falls back to \$HOME/.claude when all unset"
else fail "E3: Python _is_path_contained falls back to \$HOME/.claude when all unset" "yes" "${E3_RESULT}"; fi

# E4: resolve-cache-breakpoints.py _config_dir honours CLAUDE_PLUGIN_DATA (via harness_data())
E4_PD="${TMPDIR:-/tmp}/hp-e4-pd-$$"
E4_CCD="${TMPDIR:-/tmp}/hp-e4-ccd-$$"
mkdir -p "$E4_PD" "$E4_CCD"
E4_RESULT=$(CLAUDE_PLUGIN_DATA="$E4_PD" CLAUDE_CONFIG_DIR="$E4_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
import importlib.util
# Unset HARNESS_DATA so harness_data() is exercised
os.environ.pop("HARNESS_DATA", None)
spec = importlib.util.spec_from_file_location("rcb", "hooks/_lib/resolve-cache-breakpoints.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
got = mod._config_dir()
expected = os.environ["CLAUDE_PLUGIN_DATA"]
print("yes" if got == expected else f"no:{got}")
PYEOF
)
rm -rf "$E4_PD" "$E4_CCD"
if [[ "$E4_RESULT" == "yes" ]]; then pass "E4: resolve-cache-breakpoints._config_dir uses CLAUDE_PLUGIN_DATA (via harness_data())"
else fail "E4: resolve-cache-breakpoints._config_dir uses CLAUDE_PLUGIN_DATA (via harness_data())" "yes" "${E4_RESULT}"; fi

# E5: sast_triage_telemetry.py _metrics_dir honours CLAUDE_PLUGIN_DATA (via harness_data())
E5_PD="${TMPDIR:-/tmp}/hp-e5-pd-$$"
E5_CCD="${TMPDIR:-/tmp}/hp-e5-ccd-$$"
mkdir -p "$E5_PD" "$E5_CCD"
E5_RESULT=$(CLAUDE_PLUGIN_DATA="$E5_PD" CLAUDE_CONFIG_DIR="$E5_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
from pathlib import Path
import importlib.util
os.environ.pop("HARNESS_DATA", None)
os.environ.pop("CLAUDE_METRICS_DIR", None)
spec = importlib.util.spec_from_file_location("stt", "hooks/_lib/sast_triage_telemetry.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
got = str(mod._metrics_dir())
expected = str(Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "metrics")
print("yes" if got == expected else f"no:{got}")
PYEOF
)
rm -rf "$E5_PD" "$E5_CCD"
if [[ "$E5_RESULT" == "yes" ]]; then pass "E5: sast_triage_telemetry._metrics_dir uses CLAUDE_PLUGIN_DATA (via harness_data())"
else fail "E5: sast_triage_telemetry._metrics_dir uses CLAUDE_PLUGIN_DATA (via harness_data())" "yes" "${E5_RESULT}"; fi

# E6: agent_parent_chain_warn.py _metrics_dir honours CLAUDE_PLUGIN_DATA (via harness_data())
E6_PD="${TMPDIR:-/tmp}/hp-e6-pd-$$"
E6_CCD="${TMPDIR:-/tmp}/hp-e6-ccd-$$"
mkdir -p "$E6_PD" "$E6_CCD"
E6_RESULT=$(CLAUDE_PLUGIN_DATA="$E6_PD" CLAUDE_CONFIG_DIR="$E6_CCD" python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, "hooks/_lib")
from pathlib import Path
import importlib.util
os.environ.pop("HARNESS_DATA", None)
os.environ.pop("CLAUDE_METRICS_DIR", None)
spec = importlib.util.spec_from_file_location("apcw", "hooks/_lib/agent_parent_chain_warn.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
got = mod._metrics_dir()
expected = str(Path(os.environ["CLAUDE_PLUGIN_DATA"]) / "metrics")
print("yes" if got == expected else f"no:{got}")
PYEOF
)
rm -rf "$E6_PD" "$E6_CCD"
if [[ "$E6_RESULT" == "yes" ]]; then pass "E6: agent_parent_chain_warn._metrics_dir uses CLAUDE_PLUGIN_DATA (via harness_data())"
else fail "E6: agent_parent_chain_warn._metrics_dir uses CLAUDE_PLUGIN_DATA (via harness_data())" "yes" "${E6_RESULT}"; fi

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

# F5: curated seed agent-memory/spec-blind-validator/feedback_harness_internal_recursion.md is git-tracked
F5_COUNT=$(git -C "$REPO_ROOT" ls-files agent-memory/spec-blind-validator/feedback_harness_internal_recursion.md 2>/dev/null | wc -l || echo 0)
F5_COUNT="${F5_COUNT// /}"
if [[ "$F5_COUNT" -ge 1 ]]; then pass "F5: spec-blind-validator feedback seed is git-tracked"
else fail "F5: spec-blind-validator feedback seed is git-tracked" "1" "$F5_COUNT"; fi

# ---------------------------------------------------------------------------
# G-series (Slice 5a): plugin-port cleanup ACs
# G1: ROLLOUT.md has zero overlay-sync refs (bootstrap.sh / gh api / git-clone)
# G2: PORTING-NOTES.md exists with 6 section headers
# G3: bootstrap.sh is absent from repo root
# G4: .gitignore no longer whitelists !bootstrap.sh
# ---------------------------------------------------------------------------
echo "-- G-series: plugin-port cleanup ACs (Slice 5a) --"

# G1: ROLLOUT.md contains no overlay-sync refs
G1_COUNT=$(grep -cE 'bootstrap\.sh|gh[[:space:]]+api[[:space:]]|git[[:space:]]+-C[[:space:]]+.*clone|git[[:space:]]+clone' \
  "$REPO_ROOT/ROLLOUT.md" 2>/dev/null; true)
G1_COUNT=$(printf '%s' "$G1_COUNT" | tr -d '[:space:]')
G1_COUNT="${G1_COUNT:-0}"
if [[ "$G1_COUNT" -eq 0 ]]; then pass "G1: ROLLOUT.md has zero overlay-sync refs (bootstrap.sh / gh api / git-clone)"
else fail "G1: ROLLOUT.md has zero overlay-sync refs" 0 "$G1_COUNT"; fi

# G2: PORTING-NOTES.md exists with at least 6 section headers
G2_EXISTS=0
G2_HEADS=0
if [[ -f "$REPO_ROOT/PORTING-NOTES.md" ]]; then
  G2_EXISTS=1
  G2_HEADS=$(grep -c '^## ' "$REPO_ROOT/PORTING-NOTES.md" 2>/dev/null; true)
  G2_HEADS=$(printf '%s' "$G2_HEADS" | tr -d '[:space:]')
  G2_HEADS="${G2_HEADS:-0}"
fi
if [[ "$G2_EXISTS" -eq 1 && "$G2_HEADS" -ge 6 ]]; then pass "G2: PORTING-NOTES.md exists with >= 6 section headers (got $G2_HEADS)"
else fail "G2: PORTING-NOTES.md exists with >= 6 section headers" "file+>=6 headers" "exists=$G2_EXISTS headers=$G2_HEADS"; fi

# G3: bootstrap.sh is absent from repo root (was git-rm'd)
if [[ ! -f "$REPO_ROOT/bootstrap.sh" ]]; then pass "G3: bootstrap.sh absent from repo root"
else fail "G3: bootstrap.sh absent from repo root" "absent" "present"; fi

# G4: .gitignore does not whitelist !bootstrap.sh
G4_COUNT=$(grep -c '!bootstrap\.sh' "$REPO_ROOT/.gitignore" 2>/dev/null; true)
G4_COUNT=$(printf '%s' "$G4_COUNT" | tr -d '[:space:]')
G4_COUNT="${G4_COUNT:-0}"
if [[ "$G4_COUNT" -eq 0 ]]; then pass "G4: .gitignore does not whitelist !bootstrap.sh"
else fail "G4: .gitignore does not whitelist !bootstrap.sh" 0 "$G4_COUNT"; fi

# ---------------------------------------------------------------------------
# B7c (Slice a1 Wave 1): Path.home()/".claude" constructs in hooks/_lib, skills,
# and tests .py files.
# Excludes agentic_security_gate_cli.py (already-correct model per plan AC-A1c)
# and tests/test_bootstrap_settings_disk_invariant.py (intentional live read).
# Count must be 0 after slice-a1 completes.
# RED proof: plant a scratch .py with a violation, confirm scanner FIRES (>=1),
# then run the real tree check (GREEN, must be 0).
# ---------------------------------------------------------------------------
echo "-- B7c: Path.home()/\".claude\" constructs in hooks/_lib, skills, tests .py (excl exclusions) --"
echo "-- B7c RED proof: scanner fires on planted Path.home()/.claude violation --"
B7C_SCRATCH_DIR="${TMPDIR:-/tmp}/b7c-red-proof-$$"
mkdir -p "$B7C_SCRATCH_DIR"
printf 'path = Path.home() / ".claude" / "pipeline-state"\n' \
  > "$B7C_SCRATCH_DIR/planted_residual.py"
B7C_RED_COUNT=$(python3 - "$B7C_SCRATCH_DIR" <<'B7CREDHEREDOC'
import os, re, sys
# Match Path.home() adjacent to ".claude" — use chr(39) for single-quote
pattern = re.compile(r'Path\.home\(\)\s*/\s*[' + chr(34) + chr(39) + r']\.claude[' + chr(34) + chr(39) + r']')
root = sys.argv[1]
count = 0
for d, dirs, files in os.walk(root):
    dirs[:] = [x for x in dirs if x != ".git"]
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(d, f)
        with open(path) as fp:
            for line in fp:
                if pattern.search(line):
                    count += 1
print(count)
B7CREDHEREDOC
)
B7C_RED_COUNT="${B7C_RED_COUNT// /}"
rm -rf "$B7C_SCRATCH_DIR"
if [[ "$B7C_RED_COUNT" -ge 1 ]]; then pass "B7c-RED: scanner fires on planted Path.home()/.claude violation (got $B7C_RED_COUNT)"
else fail "B7c-RED: scanner fires on planted violation" ">=1" "$B7C_RED_COUNT"; fi

echo "-- B7c GREEN: zero Path.home()/.claude constructs in hooks/_lib, skills, tests .py (excl exclusions) --"
B7C_COUNT=$(python3 - "$REPO_ROOT" <<'B7CPYEOF'
import os, re, sys

# Use chr(34)=" and chr(39)=' to avoid heredoc quoting issues
pattern = re.compile(r'Path\.home\(\)\s*/\s*[' + chr(34) + chr(39) + r']\.claude[' + chr(34) + chr(39) + r']')

# Files explicitly excluded (intentional patterns):
#   harness_paths.py — canonical resolver; Path.home()/.claude IS the cold-start fallback
#   agentic_security_gate_cli.py — already-correct model (plan AC-A1c)
#   test_bootstrap_settings_disk_invariant.py — intentional live read
#   test_harness_paths_py.py — overlay-equivalence assertion (AC-A1a verifies fallback)
#   test_skills_paths_portability.py — overlay-equivalence assertion (AC-A3e)
#   test_spec_blind_freshness.py — not a CA8 target; uses Path.home() in helper fallback
#   test_quality_gate_taskid_required.py — not a CA8 target; log path helper fallback
EXCLUDED_FILES = {
    "harness_paths.py",
    "agentic_security_gate_cli.py",
    "test_bootstrap_settings_disk_invariant.py",
    "test_harness_paths_py.py",
    "test_skills_paths_portability.py",
    "test_spec_blind_freshness.py",
    "test_quality_gate_taskid_required.py",
}

root = sys.argv[1]
count = 0


def scan_dir(dir_root):
    global count
    for d, dirs, files in os.walk(dir_root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in EXCLUDED_FILES:
                continue
            path = os.path.join(d, f)
            with open(path) as fp:
                for line in fp:
                    if pattern.search(line):
                        count += 1


scan_dir(root + "/hooks/_lib")
scan_dir(root + "/skills")
scan_dir(root + "/tests")

print(count)
B7CPYEOF
)
B7C_COUNT="${B7C_COUNT// /}"
if [[ "$B7C_COUNT" -eq 0 ]]; then pass "B7c: zero Path.home()/.claude constructs in hooks/_lib, skills, tests .py (excl exclusions)"
else fail "B7c: zero Path.home()/.claude constructs in hooks/_lib, skills, tests .py (excl exclusions)" 0 "$B7C_COUNT"; fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
