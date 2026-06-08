#!/usr/bin/env bash
# Tests for the intake-backstop enforcement chain (task: intake-backstop-enforce).
#
# Covers:
#   SLICE A — intake-fingerprint-audit.sh marker write, session-start-bootstrap.sh
#             marker clear, intake-reminder.sh advisory-never-blocks.
#   SLICE B — intake-backstop.sh Bash work detectors (W1-W8) + Agent spawn gate.
#   SLICE C — corpus zero-false-positives.
#   SLICE D — settings.json wires both matchers.
#
# Mirrors hooks/tests/test-bash-write-guard.sh: crafted stdin JSON fed to each
# hook, asserts exit code. Plain-bash harness (the established convention in
# this dir), not a .bats file.
#
# Run: bash hooks/tests/test-intake-backstop.sh
# Exit 0 if all pass, 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

# Hermetic HARNESS_DATA so marker/pipeline state never touches the real install.
IBS_TMP=$(mktemp -d)
export CLAUDE_PLUGIN_DATA="$IBS_TMP/data"
mkdir -p "$CLAUDE_PLUGIN_DATA"
# CRITICAL: CLAUDE_SESSION_ID is deliberately NOT exported. In the real harness
# it is UNSET in the hook env, so the old `local-$$` fallback yields a fresh PID
# per hook subprocess and the writer's marker never matches the reader's lookup.
# The SID travels through the hook's stdin `.session_id` field instead. Every
# helper below injects SID via stdin JSON; MARKER is computed from that same SID
# so the assertions exercise the real round-trip channel. Re-exporting
# CLAUDE_SESSION_ID here would re-mask the exact bug AC-13 guards — do not add it.
SID="ibs-test-session"
MARKER_DIR="$CLAUDE_PLUGIN_DATA/intake-markers"
MARKER="$MARKER_DIR/$SID.marker"

# Hermetic scratch git repo (orchestrator main-tree caller context).
IBS_MAIN="$IBS_TMP/main-repo"
git init -q "$IBS_MAIN" 2>/dev/null
(cd "$IBS_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)

clear_marker() { rm -f "$MARKER" 2>/dev/null; }
write_marker() { mkdir -p "$MARKER_DIR"; touch "$MARKER"; }

echo "=== intake-backstop Test Harness ==="
echo ""

# =====================================================================
# SLICE A
# =====================================================================
echo "-- SLICE A: marker + advisory --"

# AC-8: marker written on intake (audit hook with Skill [Intake] task_id response).
# SID arrives via stdin .session_id (the real channel), NOT via env.
clear_marker
(cd "$IBS_MAIN" && \
  jq -nc --arg s "$SID" '{tool_name:"Skill",tool_response:"[Intake] task_id: foo\nrouted to T5",session_id:$s,hook_event_name:"PostToolUse"}' \
    | bash "$HOOKS_DIR/intake-fingerprint-audit.sh" > /dev/null 2>&1)
AUDIT_EXIT=$?
run_test "AC-8: audit hook exits 0 on intake" 0 "$AUDIT_EXIT"
if [[ -f "$MARKER" ]]; then pass "AC-8: marker_written_on_intake"; else fail "AC-8: marker_written_on_intake" "file" "missing"; fi

# AC-9: marker cleared on session start. SessionStart stdin carries .session_id;
# the hook must derive SID from it to clear THIS session's marker.
write_marker
(cd "$IBS_MAIN" && \
  jq -nc --arg s "$SID" '{session_id:$s,hook_event_name:"SessionStart"}' \
    | bash "$HOOKS_DIR/session-start-bootstrap.sh" > /dev/null 2>&1)
if [[ ! -f "$MARKER" ]]; then pass "AC-9: marker_cleared_on_session_start"; else fail "AC-9: marker_cleared_on_session_start" "removed" "present"; fi

# AC-1: conversational prompt never blocks (advisory hook).
CONV_OUT=$( (cd "$IBS_MAIN" && \
  jq -nc '{prompt:"how does the router work?",hook_event_name:"UserPromptSubmit"}' \
    | bash "$HOOKS_DIR/intake-reminder.sh" 2>/dev/null) )
CONV_EXIT=$?
run_test "AC-1: conversational prompt -> exit 0" 0 "$CONV_EXIT"
if [[ -z "$CONV_OUT" ]]; then pass "AC-1: conversational prompt -> empty stdout"; else fail "AC-1: conversational empty stdout" "empty" "$CONV_OUT"; fi

echo ""

# =====================================================================
# SLICE B
# =====================================================================
echo "-- SLICE B: backstop predicate --"

# Feed a Bash command to the backstop in maximally-strict state (orchestrator
# caller, no marker, no pipeline) unless overridden.
run_bash() {
  # $1=command  $2=cwd(default IBS_MAIN)  $3=subagent_type(default empty)
  #   $4=session_id(default $SID) — the marker-scoping channel.
  local cmd="$1" cwd="${2:-$IBS_MAIN}" subtype="${3:-}" sess="${4:-$SID}"
  (cd "$cwd" && \
    jq -nc --arg c "$cmd" --arg s "$subtype" --arg sid "$sess" \
      '{tool_name:"Bash",tool_input:{command:$c},subagent_type:$s,session_id:$sid,hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
}

run_agent() {
  # $1=spawn target subagent_type
  local target="$1"
  (cd "$IBS_MAIN" && \
    jq -nc --arg t "$target" --arg sid "$SID" \
      '{tool_name:"Agent",tool_input:{subagent_type:$t},session_id:$sid,hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
}

# AC-2: work bash caught when no intake.
clear_marker
run_bash "pip install requests"
run_test "AC-2: pip install (no intake) -> block (exit 2)" 2 $?

# Confirm BLOCKED stderr present.
clear_marker
BLK_ERR=$( (cd "$IBS_MAIN" && \
  jq -nc --arg sid "$SID" '{tool_name:"Bash",tool_input:{command:"pip install requests"},session_id:$sid,hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/intake-backstop.sh" 2>&1 1>/dev/null) )
if echo "$BLK_ERR" | grep -q "BLOCKED:"; then pass "AC-2: stderr has BLOCKED"; else fail "AC-2: stderr BLOCKED" "BLOCKED" "$BLK_ERR"; fi

# AC-3: same command allowed after intake (marker present). SID round-trip guard.
write_marker
run_bash "pip install requests"
run_test "AC-3: pip install (marker present) -> allow (exit 0)" 0 $?
clear_marker

# AC-4: subagent caller never blocked.
run_bash "pip install x" "$IBS_MAIN" "software-engineer"
run_test "AC-4: pip install (subagent caller) -> allow (exit 0)" 0 $?

# AC-5: read-only bash never blocked.
run_bash "git status"
run_test "AC-5: git status -> allow (exit 0)" 0 $?
run_bash "jq . foo.json"
run_test "AC-5: jq . foo.json -> allow (exit 0)" 0 $?
run_bash "cat x"
run_test "AC-5: cat x -> allow (exit 0)" 0 $?

# AC-6: architect spawn allowed.
run_agent "architect"
run_test "AC-6: architect spawn -> allow (exit 0)" 0 $?
run_agent "harness:architect"
run_test "AC-6: harness:architect spawn -> allow (exit 0)" 0 $?

# AC-6b: specialized spawn blocked when no intake.
run_agent "software-engineer"
run_test "AC-6b: software-engineer spawn (no intake) -> block (exit 2)" 2 $?
run_agent "harness:code-reviewer"
run_test "AC-6b: harness:code-reviewer spawn (no intake) -> block (exit 2)" 2 $?

# AC-7: escape env allows work bash AND specialized spawn (no marker for $SID).
clear_marker
(cd "$IBS_MAIN" && \
  jq -nc --arg sid "$SID" '{tool_name:"Bash",tool_input:{command:"pip install requests"},session_id:$sid,hook_event_name:"PreToolUse"}' \
  | CLAUDE_INTAKE_BACKSTOP=off bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
run_test "AC-7: CLAUDE_INTAKE_BACKSTOP=off + work bash -> allow (exit 0)" 0 $?
(cd "$IBS_MAIN" && \
  jq -nc --arg sid "$SID" '{tool_name:"Agent",tool_input:{subagent_type:"software-engineer"},session_id:$sid,hook_event_name:"PreToolUse"}' \
  | CLAUDE_INTAKE_BACKSTOP=off bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
run_test "AC-7: CLAUDE_INTAKE_BACKSTOP=off + specialized spawn -> allow (exit 0)" 0 $?

# AC-12: an ORPHANED/FOREIGN in_progress pipeline (different task_id, NOT this
# session, no intake marker) must NOT satisfy the gate. This reproduces the
# real-environment false-allow: the active-pipeline scan was GLOBAL and
# UNSCOPED, so one stale in_progress state file from a dead session disabled the
# gate for every later session. The fix drops that satisfier entirely.
#
# This test drives the REAL predicate path — no _psp stub. CLAUDE_PLUGIN_DATA
# (honoured by harness-paths.sh: CLAUDE_PLUGIN_DATA > CLAUDE_CONFIG_DIR >
# $HOME/.claude) points HARNESS_DATA at the hermetic temp dir, which is exactly
# the mechanism the hook reads, so the orphaned pipeline lands where
# _psp_find_active_pipelines (had it remained) would scan. Frontmatter mirrors a
# real pipeline.md (task_id/phase/verdict/timestamp/branch — no session id, the
# fact that made SID-scoping impossible). Pre-fix this asserted exit 0
# (false-allow); post-fix it asserts exit 2 (BLOCKED).
PSTATE="$CLAUDE_PLUGIN_DATA/pipeline-state/foreign-dead-task"
mkdir -p "$PSTATE"
cat > "$PSTATE/pipeline.md" <<'EOF'
---
task_id: foreign-dead-task
phase: review
verdict: in_progress
timestamp: 2026-06-08T20:33:00Z
branch: refactor/foreign-dead-task
---

## Pipeline: an orphaned pipeline from a different, dead session
- Review: in_progress
EOF
clear_marker
run_bash "pip install requests"
run_test "AC-12: orphaned_pipeline_does_not_disable_gate (block, exit 2)" 2 $?
rm -rf "$CLAUDE_PLUGIN_DATA/pipeline-state"

# AC-13: marker round-trip via stdin .session_id — the REAL-harness channel.
# Proves writer and reader agree on SID derived from stdin (NOT env CLAUDE_SESSION_ID,
# which is unset in the real hook env and whose old `local-$$` fallback diverges per
# subprocess). Drives the hooks exactly as the harness does: session_id IN the JSON.
echo "  -- AC-13: marker round-trip via stdin .session_id --"
rm -rf "$MARKER_DIR"

# (1) WRITER: feed intake-fingerprint-audit.sh a /intake response with session_id=sess-ABC.
(cd "$IBS_MAIN" && \
  jq -nc '{tool_name:"Skill",tool_response:"[Intake] task_id: rt\nrouted to T5",session_id:"sess-ABC",hook_event_name:"PostToolUse"}' \
    | bash "$HOOKS_DIR/intake-fingerprint-audit.sh" > /dev/null 2>&1)
if [[ -f "$MARKER_DIR/sess-ABC.marker" ]]; then
  pass "AC-13: writer creates intake-markers/sess-ABC.marker"
else
  fail "AC-13: writer creates sess-ABC.marker" "sess-ABC.marker" "$(ls "$MARKER_DIR" 2>/dev/null | tr '\n' ',')"
fi
# It must be SID-derived from stdin, NOT a local-$$ PID marker.
LOCAL_MARKERS=$(find "$MARKER_DIR" -name 'local-*.marker' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$LOCAL_MARKERS" -eq 0 ]]; then
  pass "AC-13: writer did NOT fall back to a local-PID marker"
else
  fail "AC-13: writer no local-PID marker" "0" "$LOCAL_MARKERS"
fi

# (2) READER same session sess-ABC, orchestrator caller, work command -> ALLOW (exit 0).
run_bash "pip install x" "$IBS_MAIN" "" "sess-ABC"
run_test "AC-13: reader (same session sess-ABC, marker found) -> allow (exit 0)" 0 $?

# (3) READER different session sess-XYZ (no marker) -> BLOCK (exit 2). Proves SID scopes the marker.
run_bash "pip install x" "$IBS_MAIN" "" "sess-XYZ"
run_test "AC-13: reader (different session sess-XYZ, no marker) -> block (exit 2)" 2 $?
rm -rf "$MARKER_DIR"

# Extra W-detector coverage (block when strict, allow read-only counterparts).
echo "  -- W1-W8 detectors --"
declare -a BLOCKS=(
  "npm install lodash"          # W1
  "bundle install"              # W1
  "pytest tests/foo_test.py"    # W2
  "npm test"                    # W2
  "npm run build"               # W3
  "cargo build"                 # W3
  "fly deploy"                  # W4
  "kubectl apply -f k8s.yaml"   # W4
  "sed -i 's/a/b/' src/app.py"  # W5
  "echo x > /etc/hosts"         # W5 (outside state dirs)
  "mkdir /opt/newthing"         # W6
  "rm src/old.py"               # W6
  "git commit -m wip"           # W7
  "git push origin main"        # W7
  "alembic upgrade head"        # W8
  "psql -c 'DROP TABLE users'"  # W8
)
clear_marker
for c in "${BLOCKS[@]}"; do
  run_bash "$c"
  run_test "W-block: [$c] -> block (exit 2)" 2 $?
done

declare -a ALLOWS=(
  "npm ls"
  "pip show requests"
  "bundle check"
  "pytest --collect-only"
  "make -n"
  "kubectl get pods"
  "terraform plan"
  "docker ps"
  "git log --oneline"
  "git diff HEAD~1"
  "gh pr view 123"
  "echo x >> $CLAUDE_PLUGIN_DATA/scratch.log"
  "source ./env.sh"
  "cd /tmp && ls"
  "grep -r foo ."
)
clear_marker
for c in "${ALLOWS[@]}"; do
  run_bash "$c"
  run_test "W-allow: [$c] -> allow (exit 0)" 0 $?
done

echo ""

# =====================================================================
# SLICE C — corpus zero false positives
# =====================================================================
echo "-- SLICE C: corpus --"

CORPUS="$HOOKS_DIR/tests/fixtures/intake-backstop-corpus.jsonl"
if [[ -f "$CORPUS" ]]; then
  clear_marker
  CORPUS_FAILS=0
  CORPUS_ROWS=0
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    cmd=$(printf '%s' "$row" | jq -r '.command // empty' 2>/dev/null)
    expected=$(printf '%s' "$row" | jq -r '.expected // empty' 2>/dev/null)
    [[ -z "$cmd" || -z "$expected" ]] && continue
    CORPUS_ROWS=$(( CORPUS_ROWS + 1 ))
    run_bash "$cmd"
    rc=$?
    want=0; [[ "$expected" == "block" ]] && want=2
    if [[ "$rc" -ne "$want" ]]; then
      CORPUS_FAILS=$(( CORPUS_FAILS + 1 ))
      echo "    CORPUS MISMATCH ($expected, got rc=$rc): $cmd"
    fi
  done < "$CORPUS"
  if [[ "$CORPUS_FAILS" -eq 0 ]]; then
    pass "AC-10: corpus_zero_false_positives ($CORPUS_ROWS rows)"
  else
    fail "AC-10: corpus_zero_false_positives" "0 mismatches/$CORPUS_ROWS" "$CORPUS_FAILS"
  fi
else
  echo "  !!! WARNING: corpus seed $CORPUS absent AND no live harvest — AC-10 SKIPPED !!!"
fi

echo ""

# =====================================================================
# SLICE D — settings wiring
# =====================================================================
echo "-- SLICE D: settings wiring --"

SETTINGS="$HOOKS_DIR/../settings.json"
if python3 -m json.tool < "$SETTINGS" >/dev/null 2>&1; then
  pass "AC-11: settings.json parses"
else
  fail "AC-11: settings.json parses" "valid" "invalid"
fi

WIRED=$(python3 - "$SETTINGS" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
bash_ok=agent_ok=False
for ev,blocks in d.get('hooks',{}).items():
    if ev!='PreToolUse': continue
    for b in blocks:
        m=b.get('matcher','')
        blob=json.dumps(b)
        if 'intake-backstop.sh' not in blob: continue
        if m=='Bash': bash_ok=True
        if m=='Agent': agent_ok=True
print('1' if (bash_ok and agent_ok) else '0')
PY
)
if [[ "$WIRED" == "1" ]]; then
  pass "AC-11: settings_wires_both_matchers (Bash + Agent)"
else
  fail "AC-11: settings_wires_both_matchers" "both" "$WIRED"
fi

# Cleanup
rm -rf "$IBS_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
