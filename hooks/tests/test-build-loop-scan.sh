#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_build_loop_scan.bats
# Tests for build-loop-scan.sh + _lib/build_loop_scan{,_cli}.py — the in-build-loop
# scan gate. Mirrors test-bash-write-guard.sh: hermetic scratch repo + worktree
# under .claude/worktrees/agent-*, run_*/pass/fail helpers, exit nonzero on any
# failure.
#
# Run from repo root: bash hooks/tests/test-build-loop-scan.sh
#
# All secret values are OBVIOUSLY FAKE: AKIAIOSFODNN7EXAMPLE (AWS's documented
# example key) and a PEM body of FAKEKEYFAKEKEYFAKEKEY. The AC1 positive fixtures
# are staged OUTSIDE hooks/tests/ and fixtures/ so the path-scoped placeholder
# exemption does NOT suppress the intended block.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$HOOKS_DIR/build-loop-scan.sh"
LIB="$HOOKS_DIR/_lib"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

echo "=== build-loop-scan Test Harness ==="
echo ""

# ---------------------------------------------------------------------------
# Python core unit tests (inline, import build_loop_scan)
# ---------------------------------------------------------------------------
echo "-- python core: build_loop_scan --"
CORE_OUT=$(PYTHONPATH="$LIB" python3 - <<'PY'
import build_loop_scan as m

ok = True
# AWS access key fires.
ok &= "aws-access-key" in m.scan_for_secrets("key = AKIAIOSFODNN7EXAMPLE")
# AWS secret env-assignment fires.
ok &= "aws-secret" in m.scan_for_secrets("AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE")
# PEM private-key header fires.
ok &= "private-key" in m.scan_for_secrets("-----BEGIN RSA PRIVATE KEY-----")
# Generic high-entropy api_key assignment fires.
ok &= "generic-secret" in m.scan_for_secrets('api_key = "abcd1234abcd1234abcd"')
# Clean text yields nothing.
ok &= m.scan_for_secrets("const total = sum(items)") == []
# is_fake_secret_marker is a pure predicate.
ok &= m.is_fake_secret_marker("AKIAIOSFODNN7EXAMPLE") is True
ok &= m.is_fake_secret_marker("AKIAREALLOOKINGKEY00") is False
# decision: secret -> BLOCKED exit 2.
d = m.decision(["aws-secret"], 0, 0, False)
ok &= d["verdict"] == "BLOCKED" and d["exit_code"] == 2
# decision: disabled -> BYPASSED exit 0 even with a secret.
d = m.decision(["aws-secret"], 0, 0, True)
ok &= d["verdict"] == "BYPASSED" and d["exit_code"] == 0
# decision: SAST findings, no secret -> FINDINGS exit 0.
d = m.decision([], 2, 0, False)
ok &= d["verdict"] == "FINDINGS" and d["exit_code"] == 0
# decision: clean -> PASSED exit 0.
d = m.decision([], 0, 0, False)
ok &= d["verdict"] == "PASSED" and d["exit_code"] == 0
print("OK" if ok else "BAD")
PY
)
if [[ "$CORE_OUT" == "OK" ]]; then pass "python core decision + scan_for_secrets behave"; else fail "python core decision + scan_for_secrets behave" "OK" "$CORE_OUT"; fi

echo ""

# ---------------------------------------------------------------------------
# Hermetic scratch repo + worktree
# ---------------------------------------------------------------------------
BLS_TMP=$(mktemp -d)
BLS_MAIN="$BLS_TMP/main-repo"
git init -q "$BLS_MAIN" 2>/dev/null
(cd "$BLS_MAIN" && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m init 2>/dev/null)
BLS_WT="$BLS_MAIN/.claude/worktrees/agent-testid"
mkdir -p "$BLS_MAIN/.claude/worktrees"
(cd "$BLS_MAIN" && git worktree add -q "$BLS_WT" -b worktree-agent-bls-testid 2>/dev/null)
(cd "$BLS_WT" && git config user.email t@t && git config user.name t)

# Isolated artifact root so we never touch real pipeline-state.
ART_ROOT="$BLS_TMP/data"
ARTIFACT="$ART_ROOT/pipeline-state/inline-build-scan-gate/build-artifacts/build-loop-scan-report.json"

# run_hook <command-string> <cwd> [extra-env]
# Pipes a PreToolUse Bash payload (with .cwd) to the hook, returns exit code.
run_hook() {
  local cmd="$1" cwd="$2"; shift 2
  (
    cd "$cwd" || return 1
    export CLAUDE_PLUGIN_DATA="$ART_ROOT"
    "$@" 2>/dev/null
    jq -nc --arg c "$cmd" --arg w "$cwd" \
      '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
      | bash "$HOOK" > /dev/null 2>&1
  )
}

# Capture stderr separately for category assertions.
run_hook_stderr() {
  local cmd="$1" cwd="$2"; shift 2
  (
    cd "$cwd" || return 1
    export CLAUDE_PLUGIN_DATA="$ART_ROOT"
    "$@" >/dev/null 2>&1
    jq -nc --arg c "$cmd" --arg w "$cwd" \
      '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
      | bash "$HOOK" 2>&1 >/dev/null
  )
}

stage_clean() {
  (cd "$BLS_WT" && git reset -q . 2>/dev/null; rm -f ./*.txt ./*.ts src/*.ts 2>/dev/null; true)
}

# ---------------------------------------------------------------------------
# AC1
# ---------------------------------------------------------------------------
echo "-- AC1: secret hard-block --"

# secret in staged worktree commit -> hard block (exit 2)
stage_clean
mkdir -p "$BLS_WT/src"
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";\n' > "$BLS_WT/src/upload.ts"
(cd "$BLS_WT" && git add src/upload.ts)
run_hook "git commit -m 'add s3 upload'" "$BLS_WT"
run_test "secret in staged worktree commit -> hard block (exit 2)" 2 $?

SERR=$(run_hook_stderr "git commit -m 'add s3 upload'" "$BLS_WT")
if echo "$SERR" | grep -q "aws-secret"; then pass "block stderr names the secret category (aws-secret)"; else fail "block stderr names the secret category (aws-secret)" "aws-secret" "$SERR"; fi

# PEM private key in staged commit -> hard block (exit 2)
stage_clean
printf -- '-----BEGIN RSA PRIVATE KEY-----\nFAKEKEYFAKEKEYFAKEKEY\n-----END RSA PRIVATE KEY-----\n' > "$BLS_WT/src/key.ts"
(cd "$BLS_WT" && git add src/key.ts)
run_hook "git commit -m 'add key'" "$BLS_WT"
run_test "PEM private key in staged commit -> hard block (exit 2)" 2 $?
SERR=$(run_hook_stderr "git commit -m 'add key'" "$BLS_WT")
if echo "$SERR" | grep -q "private-key"; then pass "PEM block stderr names private-key category"; else fail "PEM block stderr names private-key category" "private-key" "$SERR"; fi

# non-commit bash command -> allow (exit 0)
stage_clean
run_hook "ls -la" "$BLS_WT"
run_test "non-commit bash command -> allow (exit 0)" 0 $?

# git commit OUTSIDE worktree -> no-op (exit 0)
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";\n' > "$BLS_MAIN/leak.ts"
(cd "$BLS_MAIN" && git add leak.ts 2>/dev/null)
run_hook "git commit -m leak" "$BLS_MAIN"
run_test "git commit OUTSIDE worktree -> no-op (exit 0)" 0 $?
(cd "$BLS_MAIN" && git reset -q leak.ts 2>/dev/null; rm -f leak.ts)

echo ""

# ---------------------------------------------------------------------------
# AC2
# ---------------------------------------------------------------------------
echo "-- AC2: SAST advisory + SKILL Step 2c --"

# SAST finding surfaces advisory, exit 0 (only when semgrep present)
if command -v semgrep >/dev/null 2>&1; then
  stage_clean
  printf 'function run(x){ return eval(x); }\n' > "$BLS_WT/src/danger.js"
  (cd "$BLS_WT" && git add src/danger.js)
  run_hook "git commit -m danger" "$BLS_WT"
  run_test "SAST finding surfaces advisory, exit 0" 0 $?
else
  echo "  SKIP: SAST finding advisory (semgrep not installed)"
fi

# SKILL Step 2c prescribes auto-fix-or-escalate
SKILL="$HOOKS_DIR/../skills/build-implementation/SKILL.md"
if grep -q "Step 2c" "$SKILL" && grep -qi "auto-fix" "$SKILL" && grep -qi "escalate" "$SKILL" && grep -q "security-review" "$SKILL"; then
  pass "SKILL Step 2c prescribes auto-fix-or-escalate"
else
  fail "SKILL Step 2c prescribes auto-fix-or-escalate" "present" "absent"
fi

echo ""

# ---------------------------------------------------------------------------
# AC3
# ---------------------------------------------------------------------------
echo "-- AC3: security-review preserved as second-pass --"

SECREVIEW="$HOOKS_DIR/../skills/security-review/SKILL.md"
if grep -q "OWASP" "$SECREVIEW" && grep -qi "secrets" "$SECREVIEW" && grep -qi "dependency" "$SECREVIEW"; then
  pass "security-review SKILL retains OWASP/secrets/dependency rubric markers"
else
  fail "security-review SKILL retains OWASP/secrets/dependency rubric markers" "present" "absent"
fi
if grep -q "second-pass" "$SKILL"; then
  pass "SKILL Step 2c names security-review as second-pass gate"
else
  fail "SKILL Step 2c names security-review as second-pass gate" "second-pass" "absent"
fi

echo ""

# ---------------------------------------------------------------------------
# AC4 — tool-independence
# ---------------------------------------------------------------------------
echo "-- AC4: graceful skip + tool-independent secret floor --"

# Minimal PATH holding only git/jq/python3/bash/grep/sed/xargs dirs — strips
# semgrep/bearer/npm so the SAST/dep tool census is empty.
MIN_PATH=""
for bin in git jq python3 bash grep sed xargs cat mktemp dirname basename rm mkdir; do
  d=$(dirname "$(command -v "$bin" 2>/dev/null)" 2>/dev/null)
  [[ -n "$d" ]] && case ":$MIN_PATH:" in *":$d:"*) ;; *) MIN_PATH="${MIN_PATH:+$MIN_PATH:}$d" ;; esac
done

# no scan tools -> graceful SKIP/PASS, build proceeds (exit 0)
stage_clean
printf 'export const total = 42;\n' > "$BLS_WT/src/clean.ts"
(cd "$BLS_WT" && git add src/clean.ts)
( cd "$BLS_WT" && export CLAUDE_PLUGIN_DATA="$ART_ROOT" PATH="$MIN_PATH"; \
  jq -nc --arg c "git commit -m clean" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" >/dev/null 2>&1 )
run_test "no scan tools -> graceful SKIP/PASS, build proceeds (exit 0)" 0 $?
if [[ -f "$ARTIFACT" ]] && grep -Eq '"verdict":[[:space:]]*"(SKIPPED|PASSED)"' "$ARTIFACT"; then
  pass "clean no-tools artifact verdict is SKIPPED or PASSED"
else
  fail "clean no-tools artifact verdict is SKIPPED or PASSED" "SKIPPED/PASSED" "$(cat "$ARTIFACT" 2>/dev/null)"
fi

# tools absent does NOT suppress secret block (the security-critical assertion)
stage_clean
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";\n' > "$BLS_WT/src/leak2.ts"
(cd "$BLS_WT" && git add src/leak2.ts)
( cd "$BLS_WT" && export CLAUDE_PLUGIN_DATA="$ART_ROOT" PATH="$MIN_PATH"; \
  jq -nc --arg c "git commit -m leak" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" >/dev/null 2>&1 )
run_test "tools absent does NOT suppress secret block (exit 2)" 2 $?

echo ""

# ---------------------------------------------------------------------------
# AC5 — escape hatch + syntax
# ---------------------------------------------------------------------------
echo "-- AC5: escape hatch + syntax --"

# CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 -> bypass (exit 0) even with secret
stage_clean
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";\n' > "$BLS_WT/src/leak3.ts"
(cd "$BLS_WT" && git add src/leak3.ts)
LEDGER_DIR="$ART_ROOT/metrics"
( cd "$BLS_WT" && export CLAUDE_PLUGIN_DATA="$ART_ROOT" CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 CLAUDE_SESSION_ID=bls-test; \
  jq -nc --arg c "git commit -m leak" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" >/dev/null 2>&1 )
run_test "CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 -> bypass (exit 0) even with secret" 0 $?
SERR=$( cd "$BLS_WT" && export CLAUDE_PLUGIN_DATA="$ART_ROOT" CLAUDE_DISABLE_BUILD_LOOP_SCAN=1 CLAUDE_SESSION_ID=bls-test; \
  jq -nc --arg c "git commit -m leak" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" 2>&1 >/dev/null )
if echo "$SERR" | grep -qi "bypass"; then pass "bypass emits stderr notice"; else fail "bypass emits stderr notice" "bypass" "$SERR"; fi
if find "$LEDGER_DIR" -name "build-loop-scan-bypass.jsonl" 2>/dev/null | grep -q .; then
  pass "bypass writes bypass-ledger JSONL line"
else
  fail "bypass writes bypass-ledger JSONL line" "ledger" "absent"
fi

# syntax valid
bash -n "$HOOK"; run_test "bash -n hook -> exit 0" 0 $?
python3 -m py_compile "$LIB/build_loop_scan.py"; run_test "py_compile core -> exit 0" 0 $?
python3 -m py_compile "$LIB/build_loop_scan_cli.py"; run_test "py_compile cli -> exit 0" 0 $?


# ---------------------------------------------------------------------------
# AC6 -- fail-closed on CLI crash (regression: finding #1)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC6: fail-closed on CLI crash --"

# Simulate CLI crash by building a fake _lib directory with a CLI wrapper
# that exits non-zero and prints nothing. The hook must treat that as fail-closed.
FAKE_HOOK_DIR="$BLS_TMP/fake-hooks"
FAKE_LIB="$FAKE_HOOK_DIR/_lib"
mkdir -p "$FAKE_LIB"
# Copy the full real _lib for all support modules, then replace the CLI.
cp -r "$LIB"/. "$FAKE_LIB/"
# Overwrite the CLI with one that crashes (exits 1, no output).
printf 'import sys\nsys.exit(1)\n' > "$FAKE_LIB/build_loop_scan_cli.py"
# Symlink the hook script from the fake dir so HOOK_DIR resolves to FAKE_HOOK_DIR.
mkdir -p "$FAKE_HOOK_DIR"
cp "$HOOKS_DIR/build-loop-scan.sh" "$FAKE_HOOK_DIR/build-loop-scan.sh"
# Copy all support scripts the hook sources.
cp "$HOOKS_DIR/hook-profile.sh" "$FAKE_HOOK_DIR/hook-profile.sh"
FAKE_HOOK="$FAKE_HOOK_DIR/build-loop-scan.sh"

stage_clean
printf 'export const x = 1;\n' > "$BLS_WT/src/safe.ts"
(cd "$BLS_WT" && git add src/safe.ts)
CRASH_EXIT=$(
  cd "$BLS_WT"
  export CLAUDE_PLUGIN_DATA="$ART_ROOT"
  jq -nc --arg c "git commit -m safe" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$FAKE_HOOK" >/dev/null 2>&1
  echo $?
)
run_test "CLI crash -> fail-closed (exit 2)" 2 "$CRASH_EXIT"

CRASH_SERR=$(
  cd "$BLS_WT"
  export CLAUDE_PLUGIN_DATA="$ART_ROOT"
  jq -nc --arg c "git commit -m safe" --arg w "$BLS_WT" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$FAKE_HOOK" 2>&1 >/dev/null
)
if echo "$CRASH_SERR" | grep -qi "scan could not run\|blocking conservatively"; then
  pass "CLI crash stderr names conservative block"
else
  fail "CLI crash stderr names conservative block" "blocking conservatively" "$CRASH_SERR"
fi

# AC7 -- git commit --amend with staged secret -> hard block (finding #2)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC7: git commit --amend evasion --"

stage_clean
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";
' > "$BLS_WT/src/amend_leak.ts"
(cd "$BLS_WT" && git add src/amend_leak.ts)
run_hook "git commit --amend -m amend-with-secret" "$BLS_WT"
run_test "git commit --amend with staged secret -> hard block (exit 2)" 2 $?

# ---------------------------------------------------------------------------
# AC8 -- git -c / --no-pager global-flag evasion (finding #3)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC8: git global-flag evasion --"

stage_clean
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";
' > "$BLS_WT/src/flag_leak.ts"
(cd "$BLS_WT" && git add src/flag_leak.ts)
run_hook "git -c user.name=x commit -m flag-evasion" "$BLS_WT"
run_test "git -c user.name=x commit with staged secret -> hard block (exit 2)" 2 $?

stage_clean
printf 'const k = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";
' > "$BLS_WT/src/pager_leak.ts"
(cd "$BLS_WT" && git add src/pager_leak.ts)
run_hook "git --no-pager commit -m pager-evasion" "$BLS_WT"
run_test "git --no-pager commit with staged secret -> hard block (exit 2)" 2 $?

# Negative: git log with commit in format string must NOT fire.
stage_clean
run_hook "git log --format=%H --grep=commit" "$BLS_WT"
run_test "git log with commit in format/grep -> allow (exit 0)" 0 $?

# ---------------------------------------------------------------------------
# AC9 -- path parsing: b/ prefix stripped correctly (not char-class stripped) (finding #4)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC9: path parsing lstrip fix --"

PATH_OUT=$(PYTHONPATH="$LIB" python3 -c "
from build_loop_scan_cli import _added_lines

# b/build/foo.ts: correct prefix-strip gives 'build/foo.ts' (secret propagates)
# Wrong lstrip gives 'uild/foo.ts' (no fixture match, but path is corrupted)
diff_build   = '+++ b/build/foo.ts\n+const k = \"AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\";\n'
# b/fixtures/example.ts: PLACEHOLDER marker must be suppressed
diff_fixture = '+++ b/fixtures/example.ts\n+const k = \"api_key = (PLACEHOLDER_VALUE_ABCD1234ABCD1234)\";\n'
# b/backend/server.ts: correct prefix-strip gives 'backend/server.ts' (secret propagates)
# Wrong lstrip gives 'ackend/server.ts'
diff_backend = '+++ b/backend/server.ts\n+const k = \"AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\";\n'

lines_build   = _added_lines(diff_build)
lines_fixture = _added_lines(diff_fixture)
lines_backend = _added_lines(diff_backend)

# Directly verify the path-parse produces correct path string by using a
# path that lstrip would corrupt but prefix-strip would not.
# 'b/bb/file.ts' -> lstrip strips b,/,b -> '' then stops -> '' (empty, bug)
# 'b/bb/file.ts' -> prefix-strip -> 'bb/file.ts' (correct)
# We check that secrets in b/bb/ paths are still detected (not suppressed as fixture)
diff_bb = '+++ b/bb/file.ts\n+const k = \"AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\";\n'
lines_bb = _added_lines(diff_bb)

ok = True
ok = ok and any('AWS_SECRET' in l for l in lines_build)
ok = ok and (len(lines_fixture) == 0)
ok = ok and any('AWS_SECRET' in l for l in lines_backend)
ok = ok and any('AWS_SECRET' in l for l in lines_bb)
print('OK' if ok else 'BAD build={} fix={} back={} bb={}'.format(lines_build, lines_fixture, lines_backend, lines_bb))
")
if [[ "$PATH_OUT" == "OK" ]]; then
  pass "path parsing: b/ prefix-stripped correctly, b/fixtures/ suppressed, b/build/ and b/backend/ intact"
else
  fail "path parsing" "OK" "$PATH_OUT"
fi

# ---------------------------------------------------------------------------
# AC10 -- new secret shapes detected (finding #5)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC10: new secret shapes --"

NEW_SHAPES_OUT=$(PYTHONPATH="$LIB" python3 -c "
import build_loop_scan as m

results = []
results.append(('sk_live_ detected',     bool(m.scan_for_secrets('sk' + '_live_' + 'abcdefghijklmnop1234567890'))))
results.append(('ghp_ detected',          bool(m.scan_for_secrets('gh' + 'p_' + 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))))
results.append(('gho_ detected',          bool(m.scan_for_secrets('gh' + 'o_' + 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))))
results.append(('ghs_ detected',          bool(m.scan_for_secrets('gh' + 's_' + 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'))))
results.append(('xoxb- detected',         bool(m.scan_for_secrets('xox' + 'b-' + '111111111111-222222222222-abcdefghijklmnop'))))
results.append(('unquoted api_key >=16',  bool(m.scan_for_secrets('api_key=abcd1234abcd1234abcd'))))
results.append(('short unquoted no fire', not bool(m.scan_for_secrets('api_key=short'))))

failures = [name for name, ok in results if not ok]
print('OK' if not failures else 'BAD: ' + ', '.join(failures))
")
if [[ "$NEW_SHAPES_OUT" == "OK" ]]; then
  pass "new secret shapes (sk_live_, ghp_, gho_, ghs_, xoxb-, unquoted api_key)"
else
  fail "new secret shapes" "OK" "$NEW_SHAPES_OUT"
fi

# ---------------------------------------------------------------------------
# AC11 -- fail-closed when `git diff --cached` exits non-zero (Fix 1 regression)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC11: fail-closed on git-diff error --"

# Use a non-git tmpdir as the payload .cwd so `git diff --cached` returns non-zero
# (exit 128/129). The bash hook process runs from BLS_WT so is_caller_in_worktree
# passes; _staged_diff receives the non-git path from payload.cwd and fails.
# Without Fix 1 (fail-open): CLI returns PASSED/exit 0 -> hook exits 0 (WRONG).
# With Fix 1 (fail-closed): CLI raises on non-zero returncode -> exits non-zero
#   -> hook's CLI_EXIT != 0 path -> hook exits 2 (CORRECT).
NON_GIT_DIR=$(mktemp -d)

GITDIFF_EXIT=$(
  cd "$BLS_WT"
  export CLAUDE_PLUGIN_DATA="$ART_ROOT"
  jq -nc --arg c "git commit -m test-gitdiff-error" --arg w "$NON_GIT_DIR" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" >/dev/null 2>&1
  echo $?
)
run_test "git diff --cached error (non-zero git exit) -> fail-closed (exit 2)" 2 "$GITDIFF_EXIT"

GITDIFF_SERR=$(
  cd "$BLS_WT"
  export CLAUDE_PLUGIN_DATA="$ART_ROOT"
  jq -nc --arg c "git commit -m test-gitdiff-error" --arg w "$NON_GIT_DIR" \
    '{tool_name:"Bash",tool_input:{command:$c},cwd:$w,hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" 2>&1 >/dev/null
)
if echo "$GITDIFF_SERR" | grep -qi "scan could not run\|blocking conservatively"; then
  pass "git-diff error stderr names conservative block"
else
  fail "git-diff error stderr names conservative block" "blocking conservatively" "$GITDIFF_SERR"
fi

rm -rf "$NON_GIT_DIR"

# ---------------------------------------------------------------------------
# AC8-function -- _cmd_has_commit_subcommand direct function-level assertions
# (non-vacuous tokeniser test: a broken tokeniser can't hide behind a clean tree)
# ---------------------------------------------------------------------------
echo ""
echo "-- AC8-function: _cmd_has_commit_subcommand direct assertions --"

# Extract only the _cmd_has_commit_subcommand function body from the hook so we
# can source and test it in isolation without running the hook's top-level code.
FUNC_TMP=$(mktemp)
awk '/^_cmd_has_commit_subcommand\(\)/{found=1} found{print} found && /^}$/{exit}' \
  "$HOOK" > "$FUNC_TMP"

TOKENISER_OUT=$(bash -c "
  source '$FUNC_TMP'
  fail=0
  _cmd_has_commit_subcommand 'git commit'               || { echo 'FAIL: git commit'; fail=1; }
  _cmd_has_commit_subcommand 'git -c k=v commit'        || { echo 'FAIL: git -c k=v commit'; fail=1; }
  _cmd_has_commit_subcommand 'git --no-pager commit'    || { echo 'FAIL: git --no-pager commit'; fail=1; }
  _cmd_has_commit_subcommand 'git commit --amend'       || { echo 'FAIL: git commit --amend'; fail=1; }
  _cmd_has_commit_subcommand 'git log --grep=commit'    && { echo 'FAIL: git log --grep=commit should NOT match'; fail=1; }
  _cmd_has_commit_subcommand 'git push'                 && { echo 'FAIL: git push should NOT match'; fail=1; }
  _cmd_has_commit_subcommand 'git show commit'          && { echo 'FAIL: git show commit should NOT match'; fail=1; }
  # Glob-char in global-flag value must not expand; commit must still be detected.
  _cmd_has_commit_subcommand 'git -c core.pager=*.txt commit' || { echo 'FAIL: git -c core.pager=*.txt commit should MATCH'; fail=1; }
  echo \$fail
" 2>/dev/null)
rm -f "$FUNC_TMP"

if [[ "$TOKENISER_OUT" == "0" ]]; then
  pass "_cmd_has_commit_subcommand: MATCH for commit/amend/-c/--no-pager; NOMATCH for log/push/show"
else
  fail "_cmd_has_commit_subcommand direct assertions" "0 (all pass)" "$TOKENISER_OUT"
fi

# Cleanup
(cd "$BLS_MAIN" && git worktree remove --force "$BLS_WT" 2>/dev/null)
rm -rf "$BLS_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0
