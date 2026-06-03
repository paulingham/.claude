#!/usr/bin/env bash
# Regression tests for three cache-feed bugs (AssertFlip Step 0 reproducer).
# Tests are written to pass on FIXED code.
#
# Bugs covered:
#   BUG-1: cost-feed.sh exits before cache-jsonl-emit when all tokens are 0
#   BUG-2: cache-jsonl-emit.py writes to $HOME/.claude/metrics not $HARNESS_DATA/metrics
#   BUG-3: resolve-cache-breakpoints.py ignores CLAUDE_PLUGIN_ROOT for rules/core.md
#
# Run: bash hooks/tests/test-cache-feed-bugs.sh
# Exit 0 = all pass (bugs are fixed); Exit 1 = failures remain.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1"; FAIL=$(( FAIL + 1 )); }

# ── Setup ─────────────────────────────────────────────────────────────────────
TMPDIR_ROOT=$(mktemp -d)
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

FAKE_HOME="$TMPDIR_ROOT/home"
FAKE_PLUGIN_DATA="$TMPDIR_ROOT/plugin-data"
FAKE_PLUGIN_ROOT="$TMPDIR_ROOT/plugin-root"
FAKE_CONFIG_DIR="$TMPDIR_ROOT/config-dir"

mkdir -p "$FAKE_HOME/.claude/metrics"
mkdir -p "$FAKE_PLUGIN_DATA/metrics"
mkdir -p "$FAKE_PLUGIN_ROOT/rules"
mkdir -p "$FAKE_CONFIG_DIR"

# Write a fake rules/core.md under CLAUDE_PLUGIN_ROOT (plugin-install layout)
printf '# Core Rules\nTest content for hash verification.\n' > "$FAKE_PLUGIN_ROOT/rules/core.md"

FAKE_TS="2026-06-03T00:00:00Z"

echo "=== Cache Feed Bug Regression Tests ==="
echo ""

# ── BUG-1: zero-token gate decoupled from cache emit ─────────────────────────
echo "-- BUG-1: cache-jsonl-emit.py writes record even when tokens are all zero --"

FAKE_SID1="test-session-bug1"
CACHE_FILE_BUG1="$FAKE_PLUGIN_DATA/metrics/$FAKE_SID1/cache.jsonl"
mkdir -p "$FAKE_PLUGIN_DATA/metrics/$FAKE_SID1"

# Directly invoke emitter with zero tokens — emitter itself should not gate on zeros
python3 "$HOOKS_DIR/_lib/cache-jsonl-emit.py" \
  "$FAKE_PLUGIN_DATA" "$FAKE_SID1" "$FAKE_TS" "software-engineer" "0" "0" "0" 2>/dev/null

if [[ -f "$CACHE_FILE_BUG1" ]] && [[ -s "$CACHE_FILE_BUG1" ]]; then
  pass "BUG-1a: cache.jsonl written by emitter even when all token args are zero"
else
  fail "BUG-1a: cache.jsonl NOT written when token args are zero"
fi

# Verify the record has expected keys
if [[ -f "$CACHE_FILE_BUG1" ]]; then
  RECORD_OK=$(python3 -c "
import json
rec = json.loads(open('$CACHE_FILE_BUG1').readline())
required = {'ts','session_id','agent_role','input_tokens','cache_read_input_tokens','cache_creation_input_tokens','read_ratio'}
missing = required - set(rec.keys())
print('ok' if not missing else 'missing:' + ','.join(sorted(missing)))
" 2>/dev/null || echo "parse-error")
  if [[ "$RECORD_OK" == "ok" ]]; then
    pass "BUG-1b: zero-token cache.jsonl record has expected shape"
  else
    fail "BUG-1b: cache.jsonl record problem: $RECORD_OK"
  fi
fi

# Verify cost-feed.sh decouples cache emit from the zero-token early exit.
# After the fix, the zero-token guard must NOT precede the cache-emit call —
# either the guard is removed or the cache emit is hoisted above it.
FEED_CONTENT=$(<"$HOOKS_DIR/cost-feed.sh")
# Check that cache-jsonl-emit.py is called before the token-gating logic
# (or that the token gate no longer exits before the cache call).
# We verify by checking line ordering: cache emit line must appear before or
# there is no unconditional early-exit on all-zeros before it.
GATE_LINE=$(grep -n 'I_TOK.*eq 0.*O_TOK.*eq 0.*C_TOK.*eq 0.*CC_TOK.*eq 0.*exit 0' "$HOOKS_DIR/cost-feed.sh" | head -1 | cut -d: -f1)
EMIT_LINE=$(grep -n 'cache-jsonl-emit.py' "$HOOKS_DIR/cost-feed.sh" | head -1 | cut -d: -f1)
if [[ -z "$GATE_LINE" ]] || [[ -n "$EMIT_LINE" && "$EMIT_LINE" -lt "$GATE_LINE" ]]; then
  pass "BUG-1c: cache-emit call appears before (or without) the zero-token gate in cost-feed.sh"
else
  fail "BUG-1c: cache-emit call is AFTER the zero-token early-exit gate (gate at line $GATE_LINE, emit at line $EMIT_LINE)"
fi

echo ""

# ── BUG-2: cache-jsonl-emit.py uses metrics_dir arg, not hardcoded $HOME/.claude ─
echo "-- BUG-2: cache-jsonl-emit.py writes to the metrics dir passed as argv[1] --"

FAKE_SID2="test-session-bug2"
CACHE_FILE_PLUGIN="$FAKE_PLUGIN_DATA/metrics/$FAKE_SID2/cache.jsonl"
CACHE_FILE_HOME="$FAKE_HOME/.claude/metrics/$FAKE_SID2/cache.jsonl"

python3 "$HOOKS_DIR/_lib/cache-jsonl-emit.py" \
  "$FAKE_PLUGIN_DATA" "$FAKE_SID2" "$FAKE_TS" "code-reviewer" "100" "50" "20" 2>/dev/null

if [[ -f "$CACHE_FILE_PLUGIN" ]] && [[ -s "$CACHE_FILE_PLUGIN" ]]; then
  pass "BUG-2a: cache.jsonl written inside argv[1] (plugin-data) metrics dir"
else
  fail "BUG-2a: cache.jsonl NOT in plugin-data metrics dir"
fi

if [[ ! -f "$CACHE_FILE_HOME" ]]; then
  pass "BUG-2b: cache.jsonl NOT spuriously written to home/.claude/metrics"
else
  fail "BUG-2b: cache.jsonl written to home/.claude/metrics (hardcoded path still present)"
fi

# Verify cost-feed.sh passes HARNESS_DATA (not $HOME) to cache-jsonl-emit.py
EMIT_CALL=$(grep 'cache-jsonl-emit.py' "$HOOKS_DIR/cost-feed.sh" | head -1)
if echo "$EMIT_CALL" | grep -qE '\$\{?HARNESS_DATA|\$\{?METRICS_DIR'; then
  pass "BUG-2c: cost-feed.sh passes HARNESS_DATA/METRICS_DIR to cache-jsonl-emit.py (not \$HOME)"
else
  fail "BUG-2c: cost-feed.sh still passes \$HOME to cache-jsonl-emit.py — got: $EMIT_CALL"
fi

# Verify cache-jsonl-emit.py no longer hardcodes '".claude"' in the path
EMIT_PY_CONTENT=$(<"$HOOKS_DIR/_lib/cache-jsonl-emit.py")
if echo "$EMIT_PY_CONTENT" | grep -q '\.claude'; then
  fail "BUG-2d: cache-jsonl-emit.py still contains hardcoded '.claude' path segment"
else
  pass "BUG-2d: cache-jsonl-emit.py no longer hardcodes '.claude' path segment"
fi

echo ""

# ── BUG-3: resolve-cache-breakpoints.py respects CLAUDE_PLUGIN_ROOT ──────────
echo "-- BUG-3: resolve-cache-breakpoints.py finds rules/core.md via CLAUDE_PLUGIN_ROOT --"

# Scenario: only CLAUDE_PLUGIN_ROOT has rules/core.md; HARNESS_DATA and CLAUDE_CONFIG_DIR do not
PAYLOAD='{"tool_name":"Agent","tool_input":{"prompt":"test"}}'

RESULT=$(echo "$PAYLOAD" | \
  CLAUDE_PLUGIN_ROOT="$FAKE_PLUGIN_ROOT" \
  CLAUDE_PLUGIN_DATA="$FAKE_PLUGIN_DATA" \
  HARNESS_DATA="$FAKE_PLUGIN_DATA" \
  CLAUDE_CONFIG_DIR="$FAKE_CONFIG_DIR" \
  HOME="$FAKE_HOME" \
  python3 "$HOOKS_DIR/_lib/resolve-cache-breakpoints.py" 2>/dev/null)

DECISION=$(echo "$RESULT" | head -1)
ANCHORS_JSON=$(echo "$RESULT" | sed -n '2p')

if [[ "$DECISION" == "LOG" ]]; then
  pass "BUG-3a: decision=LOG for Agent tool call"
else
  fail "BUG-3a: decision=$DECISION (expected LOG)"
fi

ANCHOR_STATUS=$(python3 -c "
import json, sys
data = json.loads('''$ANCHORS_JSON''')
anchors = data.get('anchors', [])
rct = next((a for a in anchors if a['name'] == 'rules-core-tail'), None)
if rct is None:
    print('missing-anchor')
elif rct.get('status') == 'deferred' and rct.get('reason') == 'rules-core-md-missing':
    print('deferred-missing')
elif rct.get('status') == 'advisory':
    has_hash = 'segment_hash' in rct
    has_pos  = 'byte_position' in rct
    print('advisory-ok' if has_hash and has_pos else 'advisory-no-fields')
else:
    print('other:' + str(rct.get('status')))
" 2>/dev/null || echo "parse-error")

if [[ "$ANCHOR_STATUS" == "advisory-ok" ]]; then
  pass "BUG-3b: rules-core-tail is advisory with segment_hash and byte_position (found via CLAUDE_PLUGIN_ROOT)"
elif [[ "$ANCHOR_STATUS" == "deferred-missing" ]]; then
  fail "BUG-3b: rules-core-tail still deferred with 'rules-core-md-missing' (CLAUDE_PLUGIN_ROOT not checked)"
else
  fail "BUG-3b: unexpected rules-core-tail status: $ANCHOR_STATUS"
fi

# Verify source code now includes CLAUDE_PLUGIN_ROOT in _config_dir / _rules_core_anchor
RESOLVER_CONTENT=$(<"$HOOKS_DIR/_lib/resolve-cache-breakpoints.py")
if echo "$RESOLVER_CONTENT" | grep -q 'CLAUDE_PLUGIN_ROOT'; then
  pass "BUG-3c: resolve-cache-breakpoints.py references CLAUDE_PLUGIN_ROOT"
else
  fail "BUG-3c: resolve-cache-breakpoints.py does NOT reference CLAUDE_PLUGIN_ROOT"
fi

echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$(( PASS + FAIL ))
echo "=== Results: $PASS/$TOTAL passed ==="
if [[ $FAIL -gt 0 ]]; then
  echo "FAIL: $FAIL test(s) failed"
  exit 1
fi
exit 0
