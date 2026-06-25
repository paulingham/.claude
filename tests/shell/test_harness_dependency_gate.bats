#!/usr/bin/env bats
# Windows dependency gate — full AC test suite.
# AC1.1–AC1.8: probe lib (harness-dependency-check.sh)
# AC2.1–AC2.4: session-start warner (session-start-dependency-check.sh)
# AC3.1–AC3.7, AC4.1, AC7.1a/b/c: gate (harness-dependency-gate.sh)
# AC7.2: ordering assertion (dep gate before pipeline-state-guard in both registries)
#
# Hermetic setup mirrors test_main_branch_guard.bats:7-36.
# Shadow-PATH stubbing: build a fake bin/ with only the tools we want visible.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  FAKE_BIN="$(mktemp -d)"

  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-hdg-$$"

  PROBE_LIB="$REPO_ROOT/hooks/_lib/harness-dependency-check.sh"
  WARNER_LIB="$REPO_ROOT/hooks/_lib/session-start-dependency-check.sh"
  GATE="$REPO_ROOT/hooks/harness-dependency-gate.sh"
  BOOTSTRAP="$REPO_ROOT/hooks/session-start-bootstrap.sh"

  # Find a platform-agnostic 'true' binary for stubs (prefer /usr/bin/true which exists on macOS)
  if [ -x /usr/bin/true ]; then
    TRUE_BIN="/usr/bin/true"
  elif [ -x /bin/true ]; then
    TRUE_BIN="/bin/true"
  else
    echo "Cannot find executable 'true' binary at /usr/bin/true or /bin/true" >&2
    return 1
  fi

  # Build a "full-environment" fake bin with all required commands present.
  # Includes dirname (used by hook libs for self-relative sourcing).
  for cmd in bash git realpath mktemp python3 jq dirname printf sed grep cat; do
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    [ -n "$resolved" ] && ln -sf "$resolved" "$FAKE_BIN/$cmd" 2>/dev/null || true
  done
  # flock may not exist on macOS; stub it so it "resolves" as present
  if ! command -v flock >/dev/null 2>&1; then
    ln -sf "$TRUE_BIN" "$FAKE_BIN/flock"
  else
    ln -sf "$(command -v flock)" "$FAKE_BIN/flock"
  fi
  # Ensure python3 stub resolves to a real interpreter
  if ! command -v python3 >/dev/null 2>&1; then
    printf '#!/bin/sh\nexec python "$@"\n' > "$FAKE_BIN/python3"
    chmod +x "$FAKE_BIN/python3"
  fi
}

teardown() {
  rm -rf "$TMP_HOME" "$FAKE_BIN"
  unset CLAUDE_HOOK_PROFILE CLAUDE_SESSION_ID HOME
  unset CLAUDE_DISABLE_DEPENDENCY_GATE
  unset HDC_MISSING HDC_SOFT_MISSING HDC_PYTHON
}

# Helper: build a fake PATH directory with all required commands EXCEPT remove_cmd.
# Includes dirname and printf (used by hook libs) plus common POSIX tools.
_path_without() {
  local remove_cmd="$1"
  local new_bin; new_bin="$(mktemp -d)"
  local true_bin; true_bin="$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)"
  for cmd in bash git realpath mktemp flock python3 python jq dirname printf sed grep cat; do
    [ "$cmd" = "$remove_cmd" ] && continue
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    if [ -n "$resolved" ]; then
      ln -sf "$resolved" "$new_bin/$cmd" 2>/dev/null || true
    elif [ "$cmd" = "flock" ]; then
      # flock may not exist on macOS — use true stub so it "resolves"
      ln -sf "$true_bin" "$new_bin/$cmd" 2>/dev/null || true
    fi
  done
  echo "$new_bin"
}

# Helper: run the probe lib in a subshell with a restricted PATH.
# Writes a small script to a temp file to avoid quoting issues.
# WHY: uses a quoted heredoc ('PROBE_SCRIPT') so variables in the body
#      are NOT expanded at write time — they are literal shell code.
#      Then we expand only $probe_path before writing.
_run_probe() {
  local probe_path="${1:-$PROBE_LIB}"
  local probe_script; probe_script="$(mktemp /tmp/probe_test.XXXXXX.sh)"
  cat > "$probe_script" <<'PROBE_SCRIPT_BEGIN'
#!/usr/bin/env bash
PROBE_SCRIPT_BEGIN
  # Write the source line with the actual path (needs expansion)
  printf '. "%s"\n' "$probe_path" >> "$probe_script"
  cat >> "$probe_script" <<'PROBE_SCRIPT_END'
_hdc_probe
_probe_rc=$?
echo "RC=${_probe_rc}"
echo "MISSING=${HDC_MISSING:-}"
echo "SOFT=${HDC_SOFT_MISSING:-}"
echo "PYTHON=${HDC_PYTHON:-}"
exit "${_probe_rc}"
PROBE_SCRIPT_END
  chmod +x "$probe_script"
  echo "$probe_script"
}

# Helper: feed JSON into gate and capture exit status + stderr.
_run_gate() {
  local tool_name="${1:-Agent}"
  local subagent_type="${2:-software-engineer}"
  printf '{"tool_name":"%s","tool_input":{"subagent_type":"%s"}}' \
    "$tool_name" "$subagent_type" \
    | bash "$GATE" 2>&1
}

# ==============================================================================
# SLICE 1: Probe lib (AC1.1–AC1.8)
# ==============================================================================

@test "AC1.1 all-present: both HDC_MISSING and HDC_SOFT_MISSING empty, rc 0" {
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE "^RC=0$"
  echo "$output" | grep -qE "^MISSING=$"
  echo "$output" | grep -qE "^SOFT=$"
}

@test "AC1.2 git hidden: HDC_MISSING contains git, rc nonzero" {
  local no_git; no_git="$(_path_without git)"
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE "MISSING=.*git"
}

@test "AC1.3 no python interpreter: HDC_MISSING has python, HDC_PYTHON empty" {
  local no_python; no_python="$(mktemp -d)"
  local real_bash; real_bash="$(command -v bash)"
  local real_git; real_git="$(command -v git)"
  local real_realpath; real_realpath="$(command -v realpath)"
  local real_mktemp; real_mktemp="$(command -v mktemp)"
  [ -n "$real_bash" ] && ln -sf "$real_bash" "$no_python/bash"
  [ -n "$real_git" ] && ln -sf "$real_git" "$no_python/git"
  [ -n "$real_realpath" ] && ln -sf "$real_realpath" "$no_python/realpath"
  [ -n "$real_mktemp" ] && ln -sf "$real_mktemp" "$no_python/mktemp"
  # flock stub (not required on macOS)
  ln -sf "$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)" "$no_python/flock" 2>/dev/null || true
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$no_python" bash "$script"
  rm -f "$script"; rm -rf "$no_python"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE "MISSING=.*python"
  echo "$output" | grep -qE "^PYTHON=$"
}

@test "AC1.4 only 'python' (not python3): HDC_PYTHON==python, not in HDC_MISSING" {
  local py_only; py_only="$(mktemp -d)"
  local real_bash; real_bash="$(command -v bash)"
  local real_git; real_git="$(command -v git)"
  local real_realpath; real_realpath="$(command -v realpath)"
  local real_mktemp; real_mktemp="$(command -v mktemp)"
  [ -n "$real_bash" ] && ln -sf "$real_bash" "$py_only/bash"
  [ -n "$real_git" ] && ln -sf "$real_git" "$py_only/git"
  [ -n "$real_realpath" ] && ln -sf "$real_realpath" "$py_only/realpath"
  [ -n "$real_mktemp" ] && ln -sf "$real_mktemp" "$py_only/mktemp"
  # Provide only 'python', not python3
  local real_py; real_py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
  [ -n "$real_py" ] && ln -sf "$real_py" "$py_only/python"
  ln -sf "$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)" "$py_only/flock" 2>/dev/null || true
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$py_only" bash "$script"
  rm -f "$script"; rm -rf "$py_only"
  echo "$output" | grep -qE "^PYTHON=python$"
  echo "$output" | grep -qvE "MISSING=.*python"
}

@test "AC1.5 set -u safe: probe runs without unbound variable errors" {
  local script; script="$(mktemp /tmp/probe_set_u.XXXXXX.sh)"
  cat > "$script" <<PROBE_SCRIPT
#!/usr/bin/env bash
set -u
. "$PROBE_LIB"
_hdc_probe
echo "OK"
PROBE_SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  echo "$output" | grep -qvE "unbound variable"
  echo "$output" | grep -q "OK"
}

@test "AC1.6 realpath missing: HDC_MISSING contains realpath" {
  local no_realpath; no_realpath="$(_path_without realpath)"
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$no_realpath" bash "$script"
  rm -f "$script"; rm -rf "$no_realpath"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE "MISSING=.*realpath"
}

@test "AC1.6b mktemp missing: HDC_MISSING contains mktemp" {
  local no_mktemp; no_mktemp="$(_path_without mktemp)"
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$no_mktemp" bash "$script"
  rm -f "$script"; rm -rf "$no_mktemp"
  [ "$status" -ne 0 ]
  echo "$output" | grep -qE "MISSING=.*mktemp"
}

@test "AC1.7 SOFT/HARD: flock-only-missing -> HDC_SOFT_MISSING has flock, HDC_MISSING empty, rc 0" {
  local no_flock; no_flock="$(_path_without flock)"
  local script; script="$(_run_probe "$PROBE_LIB")"
  run env PATH="$no_flock" bash "$script"
  rm -f "$script"; rm -rf "$no_flock"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE "^MISSING=$"
  echo "$output" | grep -qE "SOFT=.*flock"
}

@test "AC1.8 grep-guard: probe lib sources no harness-paths/log and has no \$(python / | python call" {
  # No non-comment source/. lines that load harness-paths.sh or log.sh
  # WHY: comments may mention these files; we exclude lines starting with #
  run grep -Ev '^[[:space:]]*#' "$PROBE_LIB"
  local non_comment_lines="$output"
  if echo "$non_comment_lines" | grep -qE 'source.*harness-paths|source.*log\.sh|\. .*harness-paths|\. .*log\.sh'; then
    echo "FAIL: probe lib has source directive for harness-paths or log.sh"
    return 1
  fi
  # No $(python ...) or pipe-to-python (| python without 3/py suffix)
  if echo "$non_comment_lines" | grep -qE '\$\(python|\| python[^3]'; then
    echo "FAIL: probe lib calls python"
    return 1
  fi
}

# ==============================================================================
# SLICE 2: SessionStart Warner (AC2.1–AC2.4)
# ==============================================================================

@test "AC2.1 warner loud remediation: missing git -> stderr has Git for Windows + CLAUDE_CODE_GIT_BASH_PATH, rc 0" {
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(mktemp /tmp/warner_test.XXXXXX.sh)"
  cat > "$script" <<WARNER_SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1
echo "rc=\$?"
WARNER_SCRIPT
  chmod +x "$script"
  run env PATH="$no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "git"
  echo "$output" | grep -qi "CLAUDE_CODE_GIT_BASH_PATH"
}

@test "AC2.2 warner soft advisory: only flock missing -> stderr has flock advisory, rc 0" {
  local no_flock; no_flock="$(_path_without flock)"
  local script; script="$(mktemp /tmp/warner_soft.XXXXXX.sh)"
  cat > "$script" <<WARNER_SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1
echo "rc=\$?"
WARNER_SCRIPT
  chmod +x "$script"
  run env PATH="$no_flock" bash "$script"
  rm -f "$script"; rm -rf "$no_flock"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "flock"
  echo "$output" | grep -qi "advisory"
}

@test "AC2.3 warner silent when all present" {
  local script; script="$(mktemp /tmp/warner_silent.XXXXXX.sh)"
  cat > "$script" <<WARNER_SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1
WARNER_SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC2.4 bootstrap sources warner behind declare -F guard" {
  run grep -n "_ssdc_check_deps" "$BOOTSTRAP"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "declare -F"
  echo "$output" | grep -q "_ssdc_check_deps"
}

# ==============================================================================
# SLICE 3: Gate (AC3.1–AC3.7, AC4.1, AC7.1a/b/c)
# ==============================================================================

# Helper: build a PATH missing a specific command (no flock stub for SOFT tests).
_path_without_strict() {
  local remove_cmd="$1"
  local new_bin; new_bin="$(mktemp -d)"
  for cmd in bash git realpath mktemp python3 python; do
    [ "$cmd" = "$remove_cmd" ] && continue
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    [ -n "$resolved" ] && ln -sf "$resolved" "$new_bin/$cmd" 2>/dev/null || true
  done
  echo "$new_bin"
}

# Helper: build a gate runner script and return its path.
_gate_script() {
  local gate_path="${1:-$GATE}"
  local script; script="$(mktemp /tmp/gate_runner.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$gate_path" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  echo "$script"
}

# Helper: build a "no git" fake PATH with all hard-deps except git + POSIX utilities.
# WHY: hook libs use dirname, printf etc. which must be present in the restricted PATH.
_no_git_path() {
  local new_bin; new_bin="$(mktemp -d)"
  local true_bin; true_bin="$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)"
  for cmd in bash realpath mktemp python3 jq dirname printf sed grep cat; do
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    [ -n "$resolved" ] && ln -sf "$resolved" "$new_bin/$cmd" 2>/dev/null || true
  done
  ln -sf "$true_bin" "$new_bin/flock"
  echo "$new_bin"
}

@test "AC3.1 gate exits 2 + fixed-form block message on hard-missing dep" {
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(_gate_script "$GATE")"
  run env PATH="$no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qi "BLOCKED"
  echo "$output" | grep -qi "git"
}

@test "AC3.2 RED-ON-REVERT: gate exit 2 is the enforcing line (mutation guard)" {
  # This test verifies the gate exits 2 on missing dep.
  # When we flip exit 2 -> exit 0, this test must go RED.
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(_gate_script "$GATE")"
  run env PATH="$no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  # MUST exit 2; if the gate were changed to exit 0, this test fails
  [ "$status" -eq 2 ]
}

@test "AC3.3 gate exits 0 on healthy box" {
  local script; script="$(mktemp /tmp/gate_healthy.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
}

@test "AC3.4 gate exits 0 for non-Agent tool_name" {
  local script; script="$(mktemp /tmp/gate_nonagent.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
}

@test "AC3.5 block message is sanitized: no raw control chars in HDC_MISSING" {
  # Gate must sanitize HDC_MISSING with ${HDC_MISSING//[^a-z0-9 ]/_} before printing
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(_gate_script "$GATE")"
  run env PATH="$no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 2 ]
  # Block message should only contain safe chars (a-z, 0-9, space) in the dep names
  echo "$output" | grep -qE "BLOCKED: harness prerequisites missing: [a-z0-9 ]+"
}

@test "AC3.6 SOFT-ONLY: only flock missing -> gate exits 0 (no false-positive block)" {
  # Build a PATH with no flock but all hard deps present
  local no_flock; no_flock="$(_path_without flock)"
  local script; script="$(_gate_script "$GATE")"
  run env PATH="$no_flock" bash "$script"
  rm -f "$script"; rm -rf "$no_flock"
  [ "$status" -eq 0 ]
}

@test "AC3.7 SELF-CONTAINED: gate body sources no log.sh or harness-paths.sh (grep-guard, INV-5)" {
  run grep -E 'source.*log\.sh|source.*harness-paths|\. .*log\.sh|\. .*harness-paths' "$GATE"
  [ "$status" -ne 0 ]  # grep found nothing = gate is clean
}

@test "AC4.1 CLAUDE_DISABLE_DEPENDENCY_GATE=1 -> exit 0 + bypass log line" {
  # Even with git missing, bypass env var makes the gate exit 0
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(mktemp /tmp/gate_bypass.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$no_git" CLAUDE_DISABLE_DEPENDENCY_GATE=1 bash "$script"
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "bypass"
}

@test "AC7.1a probe lib unsourceable -> gate exits 2 SPECIFICALLY (rc==2)" {
  # Patch gate to use a nonexistent probe lib path — source fails, gate must exit 2
  local patched; patched="$(mktemp /tmp/gate_patched.XXXXXX.sh)"
  sed 's|harness-dependency-check\.sh|/nonexistent/probe.sh|g' "$GATE" > "$patched"
  chmod +x "$patched"
  local script; script="$(mktemp /tmp/gate_runner_a.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$patched" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run bash "$script"
  rm -f "$patched" "$script"
  [ "$status" -eq 2 ]
}

@test "AC7.1b HDC_MISSING never set (probe doesn't set it) -> gate exits 2 via +x set-test" {
  # Fake probe: defines _hdc_probe but never sets HDC_MISSING
  local fake_probe; fake_probe="$(mktemp /tmp/fake_probe_b.XXXXXX.sh)"
  printf '#!/usr/bin/env bash\n_hdc_probe() { return 0; }\n' > "$fake_probe"
  local patched; patched="$(mktemp /tmp/gate_patched_b.XXXXXX.sh)"
  sed "s|harness-dependency-check\.sh|$fake_probe|g" "$GATE" > "$patched"
  chmod +x "$patched"
  local script; script="$(mktemp /tmp/gate_runner_b.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$patched" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run bash "$script"
  rm -f "$fake_probe" "$patched" "$script"
  [ "$status" -eq 2 ]
}

@test "AC7.1c _hdc_probe undefined after source -> gate exits 2 (declare -F guard)" {
  # Fake probe: sources without defining _hdc_probe (but does set HDC_MISSING)
  local fake_probe; fake_probe="$(mktemp /tmp/fake_probe_c.XXXXXX.sh)"
  printf '#!/usr/bin/env bash\nHDC_MISSING=""\nHDC_SOFT_MISSING=""\nHDC_PYTHON=""\n' > "$fake_probe"
  local patched; patched="$(mktemp /tmp/gate_patched_c.XXXXXX.sh)"
  sed "s|harness-dependency-check\.sh|$fake_probe|g" "$GATE" > "$patched"
  chmod +x "$patched"
  local script; script="$(mktemp /tmp/gate_runner_c.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$patched" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run bash "$script"
  rm -f "$fake_probe" "$patched" "$script"
  [ "$status" -eq 2 ]
}

# ==============================================================================
# SLICE 4: Ordering (AC7.2)
# ==============================================================================

# ==============================================================================
# SLICE 5: Fix-cycle new tests (CRITICAL-1, CRITICAL-2, stdin edge-cases)
# ==============================================================================

# Helper: build a fake PATH with all hard deps except jq AND except remove_cmd.
# WHY: tests CRITICAL-1 fix — gate must not depend on jq.
_path_without_jq_and() {
  local remove_cmd="$1"
  local new_bin; new_bin="$(mktemp -d)"
  local true_bin; true_bin="$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)"
  for cmd in bash git realpath mktemp python3 python dirname printf sed grep cat; do
    [ "$cmd" = "$remove_cmd" ] && continue
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    [ -n "$resolved" ] && ln -sf "$resolved" "$new_bin/$cmd" 2>/dev/null || true
  done
  ln -sf "$true_bin" "$new_bin/flock" 2>/dev/null || true
  # jq intentionally omitted
  echo "$new_bin"
}

@test "CRIT1-A jq absent + git missing + tool_name:Agent -> exit 2 (CRITICAL-1 fixed; would have been exit 0 before)" {
  # WHY: old jq-based parse silently produces empty TOOL_NAME on jq-less box → exit 0 (fail-open).
  # New pure-bash parse correctly extracts "Agent" → gate proceeds → git missing → exit 2.
  local no_jq_no_git; no_jq_no_git="$(_path_without_jq_and git)"
  local script; script="$(mktemp /tmp/gate_crit1a.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$no_jq_no_git" bash "$script"
  rm -f "$script"; rm -rf "$no_jq_no_git"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qi "BLOCKED"
}

@test "CRIT1-B jq absent + tool_name:Agent + ALL hard deps present -> exit 0 (no false-positive from pure-bash parser)" {
  # WHY: confirms the pure-bash parser doesn't cause false blocks when everything is installed.
  local no_jq; no_jq="$(_path_without_jq_and NOTHING)"
  local script; script="$(mktemp /tmp/gate_crit1b.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$no_jq:$PATH" bash "$script"
  rm -f "$script"; rm -rf "$no_jq"
  [ "$status" -eq 0 ]
}

@test "CRIT1-C empty stdin -> exit 0 (treated as non-Agent; conscious decision matches harness convention)" {
  # WHY: unparseable/empty input → TOOL_NAME="" → non-Agent → exit 0.
  # This is intentional: an empty stdin is not an Agent spawn.
  local script; script="$(mktemp /tmp/gate_crit1c.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
}

@test "CRIT1-D garbage non-JSON stdin -> exit 0 (treated as non-Agent; conscious decision matches harness convention)" {
  # WHY: corrupt/non-JSON input → pure-bash regex finds no tool_name → TOOL_NAME="" → exit 0.
  # Gate must not crash or block on bad input that isn't an Agent spawn.
  local script; script="$(mktemp /tmp/gate_crit1d.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf 'not json at all !!!' | bash "$GATE" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
}

@test "CRIT2 sourceable-but-empty hook-profile.sh (check_hook_profile undefined) + hard dep missing -> exit 2 (CRITICAL-2 fixed)" {
  # WHY: old code called check_hook_profile "minimal" || exit 0 without checking existence.
  # If hook-profile.sh is empty/truncated, check_hook_profile is undefined → || exit 0 fires → fail-open.
  # New declare -F guard catches this and exits 2 instead.
  local fake_profile; fake_profile="$(mktemp /tmp/fake_profile.XXXXXX.sh)"
  printf '#!/usr/bin/env bash\n# empty — check_hook_profile NOT defined\n' > "$fake_profile"
  local patched; patched="$(mktemp /tmp/gate_crit2.XXXXXX.sh)"
  sed "s|hook-profile\.sh|$fake_profile|g" "$GATE" > "$patched"
  chmod +x "$patched"
  local no_git; no_git="$(_no_git_path)"
  local script; script="$(mktemp /tmp/gate_runner_crit2.XXXXXX.sh)"
  cat > "$script" <<GATE_SCRIPT
#!/usr/bin/env bash
printf '{"tool_name":"Agent","tool_input":{"subagent_type":"x"}}' | bash "$patched" 2>&1
GATE_SCRIPT
  chmod +x "$script"
  run env PATH="$no_git" bash "$script"
  rm -f "$fake_profile" "$patched" "$script"; rm -rf "$no_git"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qi "BLOCKED"
}

@test "AC7.2 ORDERING: dep gate index < pipeline-state-guard index in BOTH Agent arrays" {
  command -v python3 || skip "python3 required for ordering check"
  run python3 - "$REPO_ROOT/hooks/hooks.json" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)

agent_blocks = [
    b for b in data.get("hooks", {}).get("PreToolUse", [])
    if b.get("matcher") == "Agent"
]
assert len(agent_blocks) == 1, f"Expected 1 Agent block, got {len(agent_blocks)}"
hooks = agent_blocks[0]["hooks"]

def find_index(basename, hooks):
    for i, h in enumerate(hooks):
        for arg in h.get("args", []):
            if basename in arg:
                return i
    return -1

dep_idx = find_index("harness-dependency-gate.sh", hooks)
psg_idx = find_index("pipeline-state-guard.sh", hooks)

assert dep_idx >= 0, "harness-dependency-gate.sh not found in hooks.json Agent block"
assert psg_idx >= 0, "pipeline-state-guard.sh not found in hooks.json Agent block"
assert dep_idx < psg_idx, \
    f"harness-dependency-gate.sh (idx={dep_idx}) must precede pipeline-state-guard.sh (idx={psg_idx})"
print(f"OK: dep_gate={dep_idx} < psg={psg_idx}")
PYEOF
  [ "$status" -eq 0 ]

  run python3 - "$REPO_ROOT/settings.json" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)

agent_blocks = [
    b for b in data.get("hooks", {}).get("PreToolUse", [])
    if b.get("matcher") == "Agent"
]
assert len(agent_blocks) == 1, f"Expected 1 Agent block, got {len(agent_blocks)}"
hooks = agent_blocks[0]["hooks"]

def find_index(basename, hooks):
    for i, h in enumerate(hooks):
        for arg in h.get("args", []):
            if basename in arg:
                return i
    return -1

dep_idx = find_index("harness-dependency-gate.sh", hooks)
psg_idx = find_index("pipeline-state-guard.sh", hooks)

assert dep_idx >= 0, "harness-dependency-gate.sh not found in settings.json Agent block"
assert psg_idx >= 0, "pipeline-state-guard.sh not found in settings.json Agent block"
assert dep_idx < psg_idx, \
    f"harness-dependency-gate.sh (idx={dep_idx}) must precede pipeline-state-guard.sh (idx={psg_idx})"
print(f"OK: dep_gate={dep_idx} < psg={psg_idx}")
PYEOF
  [ "$status" -eq 0 ]
}
