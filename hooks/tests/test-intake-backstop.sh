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
# Stable, sanitisable session id for the marker round-trip.
export CLAUDE_SESSION_ID="ibs-test-session"
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
clear_marker
(cd "$IBS_MAIN" && \
  jq -nc '{tool_name:"Skill",tool_response:"[Intake] task_id: foo\nrouted to T5",hook_event_name:"PostToolUse"}' \
    | bash "$HOOKS_DIR/intake-fingerprint-audit.sh" > /dev/null 2>&1)
AUDIT_EXIT=$?
run_test "AC-8: audit hook exits 0 on intake" 0 "$AUDIT_EXIT"
if [[ -f "$MARKER" ]]; then pass "AC-8: marker_written_on_intake"; else fail "AC-8: marker_written_on_intake" "file" "missing"; fi

# AC-9: marker cleared on session start.
write_marker
(cd "$IBS_MAIN" && bash "$HOOKS_DIR/session-start-bootstrap.sh" > /dev/null 2>&1)
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
  local cmd="$1" cwd="${2:-$IBS_MAIN}" subtype="${3:-}"
  (cd "$cwd" && \
    jq -nc --arg c "$cmd" --arg s "$subtype" \
      '{tool_name:"Bash",tool_input:{command:$c},subagent_type:$s,hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
}

run_agent() {
  # $1=spawn target subagent_type
  local target="$1"
  (cd "$IBS_MAIN" && \
    jq -nc --arg t "$target" \
      '{tool_name:"Agent",tool_input:{subagent_type:$t},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
}

# AC-2: work bash caught when no intake.
clear_marker
run_bash "pip install requests"
run_test "AC-2: pip install (no intake) -> block (exit 2)" 2 $?

# Confirm BLOCKED stderr present.
clear_marker
BLK_ERR=$( (cd "$IBS_MAIN" && \
  jq -nc '{tool_name:"Bash",tool_input:{command:"pip install requests"},hook_event_name:"PreToolUse"}' \
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

# AC-7: escape env allows work bash AND specialized spawn.
(cd "$IBS_MAIN" && CLAUDE_INTAKE_BACKSTOP=off \
  jq -nc '{tool_name:"Bash",tool_input:{command:"pip install requests"},hook_event_name:"PreToolUse"}' \
  | CLAUDE_INTAKE_BACKSTOP=off bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
run_test "AC-7: CLAUDE_INTAKE_BACKSTOP=off + work bash -> allow (exit 0)" 0 $?
(cd "$IBS_MAIN" && \
  jq -nc '{tool_name:"Agent",tool_input:{subagent_type:"software-engineer"},hook_event_name:"PreToolUse"}' \
  | CLAUDE_INTAKE_BACKSTOP=off bash "$HOOKS_DIR/intake-backstop.sh" > /dev/null 2>&1)
run_test "AC-7: CLAUDE_INTAKE_BACKSTOP=off + specialized spawn -> allow (exit 0)" 0 $?

# AC-7b: active pipeline allows work bash (stub a pipeline-state dir).
PSTATE="$CLAUDE_PLUGIN_DATA/pipeline-state/stub-task"
mkdir -p "$PSTATE"
cat > "$PSTATE/pipeline.md" <<'EOF'
# Pipeline: stub-task
task_id: stub-task
- Build: in_progress
verdict: in_progress
EOF
clear_marker
run_bash "pip install requests"
run_test "AC-7b: active pipeline + work bash -> allow (exit 0)" 0 $?
rm -rf "$CLAUDE_PLUGIN_DATA/pipeline-state"

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
