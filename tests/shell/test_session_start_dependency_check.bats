#!/usr/bin/env bats
# Verbose session-start dependency report — test suite.
bats_require_minimum_version 1.5.0
# AC1: default-path invariant (CLAUDE_VERBOSE_DEPS unset/!=1 unchanged behaviour)
# AC2: verbose report format and content (CLAUDE_VERBOSE_DEPS=1)
#
# Hermetic setup mirrors test_harness_dependency_gate.bats shadow-PATH scaffolding.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  FAKE_BIN="$(mktemp -d)"

  mkdir -p "$TMP_HOME/.claude"
  rm -rf "$TMP_HOME/.claude/hooks"
  ln -sfn "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_HOOK_PROFILE="minimal"
  export CLAUDE_SESSION_ID="bats-ssdc-$$"

  PROBE_LIB="$REPO_ROOT/hooks/_lib/harness-dependency-check.sh"
  WARNER_LIB="$REPO_ROOT/hooks/_lib/session-start-dependency-check.sh"

  # Find a platform-agnostic 'true' binary
  if [ -x /usr/bin/true ]; then
    TRUE_BIN="/usr/bin/true"
  elif [ -x /bin/true ]; then
    TRUE_BIN="/bin/true"
  else
    echo "Cannot find executable 'true' binary" >&2
    return 1
  fi

  # Build a "full-environment" fake bin with all required commands present.
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
  unset CLAUDE_VERBOSE_DEPS
  unset HDC_MISSING HDC_SOFT_MISSING HDC_PYTHON
  unset HDC_FEATURE_PRESENT HDC_FEATURE_MISSING HDC_FEATURE_MARKS
}

# Helper: build a fake PATH directory with all required commands EXCEPT remove_cmd.
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
      ln -sf "$true_bin" "$new_bin/$cmd" 2>/dev/null || true
    fi
  done
  echo "$new_bin"
}

# Helper: run _ssdc_check_deps in a subshell with controlled PATH and env.
# Arguments: extra PATH dirs (prepended), env vars as KEY=VALUE pairs.
# Prints stdout+stderr separated by ---STDERR--- marker.
_run_ssdc() {
  local extra_path="${1:-$FAKE_BIN:$PATH}"
  local verbose_val="${2:-}"
  local script; script="$(mktemp /tmp/ssdc_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
SCRIPT
  if [ -n "$verbose_val" ]; then
    printf 'CLAUDE_VERBOSE_DEPS=%s _ssdc_check_deps\n' "$verbose_val" >> "$script"
  else
    printf '_ssdc_check_deps\n' >> "$script"
  fi
  chmod +x "$script"
  echo "$script"
}

# ==============================================================================
# AC1 DEFAULT PATH INVARIANT
# ==============================================================================

@test "AC1-default-silent: CLAUDE_VERBOSE_DEPS unset + all hard deps present -> prints nothing, rc 0" {
  # RED-ON-REVERT: if verbose becomes default, this test fails because output would not be empty
  local script; script="$(_run_ssdc "$FAKE_BIN:$PATH")"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "AC1-default-preserved: CLAUDE_VERBOSE_DEPS unset + git missing -> prints MISSING-REQUIRED warning naming CLAUDE_CODE_GIT_BASH_PATH" {
  local no_git; no_git="$(_path_without git)"
  local script; script="$(_run_ssdc)"
  run env PATH="$no_git" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qi "MISSING REQUIRED"
  echo "$output" | grep -qi "CLAUDE_CODE_GIT_BASH_PATH"
}

@test "AC1-verbose-report: CLAUDE_VERBOSE_DEPS=1 -> stderr has hard: soft: and feature: lines, rc 0" {
  local script; script="$(_run_ssdc "$FAKE_BIN:$PATH" "1")"
  run env PATH="$FAKE_BIN:$PATH" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "hard:"
  echo "$output" | grep -q "soft:"
  echo "$output" | grep -q "feature:"
}

@test "AC1-verbose-stderr-only: verbose report appears on fd 2 only, not stdout" {
  local script; script="$(mktemp /tmp/ssdc_stderr_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  # WHY: use --separate-stderr so bats captures stdout into $output and stderr into $stderr
  # separately. Then assert $output (stdout) is empty while $stderr has the report.
  run --separate-stderr env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
  # stdout should be empty — report is on stderr only
  [ -z "$output" ]
  # stderr should have the report
  echo "$stderr" | grep -q "hard:"
}

@test "AC1-verbose-compact: verbose output is at most 4 lines" {
  local script; script="$(mktemp /tmp/ssdc_compact_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps 2>&1 | wc -l
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
  local line_count="${output// /}"
  [ "$line_count" -le 4 ]
}

# ==============================================================================
# AC2 FEATURE PROBE CONTENT
# ==============================================================================

@test "AC2-present: rtk stubbed onto PATH -> feature line shows rtk+" {
  local bin_with_rtk; bin_with_rtk="$(mktemp -d)"
  # Copy all FAKE_BIN entries
  for f in "$FAKE_BIN"/*; do
    [ -e "$f" ] && ln -sf "$(readlink "$f" 2>/dev/null || echo "$f")" "$bin_with_rtk/$(basename "$f")" 2>/dev/null || true
  done
  # Add a stub rtk
  ln -sf "$TRUE_BIN" "$bin_with_rtk/rtk"
  local script; script="$(mktemp /tmp/ssdc_rtk_present.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_with_rtk:$PATH" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_with_rtk"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "feature:"
  echo "$output" | grep "feature:" | grep -q "rtk+"
}

@test "AC2-absent: rtk off PATH -> feature line shows rtk-, rc still 0" {
  local bin_without_rtk; bin_without_rtk="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_rtk_absent.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_without_rtk" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -rf "$bin_without_rtk"
  rm -f "$script"
  [ "$status" -eq 0 ]
  echo "$output" | grep "feature:" | grep -q "rtk-"
}

@test "AC2-coverage: feature line names all 7 tools (rtk gh hcom dippy parry-guard typescript-language-server pyright)" {
  local script; script="$(mktemp /tmp/ssdc_coverage.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  local feature_line; feature_line="$(echo "$output" | grep "feature:")"
  echo "$feature_line" | grep -q "rtk"
  echo "$feature_line" | grep -q "gh"
  echo "$feature_line" | grep -q "hcom"
  echo "$feature_line" | grep -q "dippy"
  echo "$feature_line" | grep -q "parry-guard"
  echo "$feature_line" | grep -q "typescript-language-server"
  echo "$feature_line" | grep -q "pyright"
}

@test "AC2-gates-no-fake-vars: report never contains CLAUDE_REQUIRE_PARRY or CLAUDE_REQUIRE_HCOM" {
  local script; script="$(mktemp /tmp/ssdc_no_fake_vars.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  # Must not contain fake gate vars
  if echo "$output" | grep -q "CLAUDE_REQUIRE_PARRY"; then
    echo "FAIL: output contained CLAUDE_REQUIRE_PARRY (no such gate var exists)"
    return 1
  fi
  if echo "$output" | grep -q "CLAUDE_REQUIRE_HCOM"; then
    echo "FAIL: output contained CLAUDE_REQUIRE_HCOM (no such gate var exists)"
    return 1
  fi
}

@test "AC2-gates-conditional-both-present: rtk AND dippy both present -> NO gates: line" {
  local bin_with_rtk_dippy; bin_with_rtk_dippy="$(mktemp -d)"
  for f in "$FAKE_BIN"/*; do
    [ -e "$f" ] && ln -sf "$(readlink "$f" 2>/dev/null || echo "$f")" "$bin_with_rtk_dippy/$(basename "$f")" 2>/dev/null || true
  done
  ln -sf "$TRUE_BIN" "$bin_with_rtk_dippy/rtk"
  ln -sf "$TRUE_BIN" "$bin_with_rtk_dippy/dippy"
  local script; script="$(mktemp /tmp/ssdc_gates_both_present.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_with_rtk_dippy:$PATH" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_with_rtk_dippy"
  [ "$status" -eq 0 ]
  # When both rtk AND dippy are present, NO gates: line should appear
  if echo "$output" | grep -q "gates:"; then
    echo "FAIL: gates: line appeared even though rtk AND dippy are both present"
    return 1
  fi
}

@test "AC2-gates-conditional-rtk-missing: rtk missing -> gates: line present naming CLAUDE_REQUIRE_RTK" {
  local bin_no_rtk; bin_no_rtk="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_gates_rtk_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_no_rtk" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_no_rtk"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "gates:"
  echo "$output" | grep "gates:" | grep -q "CLAUDE_REQUIRE_RTK"
}

@test "M1-dippy-missing-alone: dippy missing + rtk present -> gates: line names CLAUDE_REQUIRE_DIPPY only" {
  # WHY: M1 missing limb — mirrors AC2-gates-conditional-rtk-missing for dippy.
  # RED-ON-REVERT: if dippy detection is removed from _ssdc_maybe_print_gates_line, this fails.
  local bin_with_rtk_no_dippy; bin_with_rtk_no_dippy="$(_path_without dippy)"
  # Add rtk stub so only dippy is missing
  ln -sf "$TRUE_BIN" "$bin_with_rtk_no_dippy/rtk"
  local script; script="$(mktemp /tmp/ssdc_gates_dippy_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_with_rtk_no_dippy" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_with_rtk_no_dippy"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "gates:"
  echo "$output" | grep "gates:" | grep -q "CLAUDE_REQUIRE_DIPPY"
  # Must NOT name CLAUDE_REQUIRE_RTK since rtk is present
  if echo "$output" | grep "gates:" | grep -q "CLAUDE_REQUIRE_RTK"; then
    echo "FAIL: gates: line named CLAUDE_REQUIRE_RTK but rtk was present"
    return 1
  fi
}

@test "AC2-python-alias-display: when only 'python' resolves, hard line shows python+(python)" {
  # Build a restricted PATH with all hard tools except python3 (only 'python' provided).
  # WHY: must include dirname because session-start-dependency-check.sh sources harness-
  #      dependency-check.sh using dirname; without it the WARNER sourcing silently fails.
  local py_only; py_only="$(mktemp -d)"
  local real_bash; real_bash="$(command -v bash)"
  local real_git; real_git="$(command -v git)"
  local real_realpath; real_realpath="$(command -v realpath)"
  local real_mktemp; real_mktemp="$(command -v mktemp)"
  local real_dirname; real_dirname="$(command -v dirname)"
  [ -n "$real_bash" ] && ln -sf "$real_bash" "$py_only/bash"
  [ -n "$real_git" ] && ln -sf "$real_git" "$py_only/git"
  [ -n "$real_realpath" ] && ln -sf "$real_realpath" "$py_only/realpath"
  [ -n "$real_mktemp" ] && ln -sf "$real_mktemp" "$py_only/mktemp"
  [ -n "$real_dirname" ] && ln -sf "$real_dirname" "$py_only/dirname"
  # Stub flock (not available on macOS)
  local true_bin; true_bin="$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)"
  ln -sf "$true_bin" "$py_only/flock" 2>/dev/null || true
  # Provide only 'python', not python3 — mirrors AC1.4 setup
  local real_py; real_py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
  [ -n "$real_py" ] && ln -sf "$real_py" "$py_only/python"
  local script; script="$(mktemp /tmp/ssdc_py_alias.XXXXXX.sh)"
  # WHY: use _path_without rather than a direct script heredoc so we source the LIBs
  # directly (not re-sourcing via dirname), avoiding the dirname dependency in the script.
  cat > "$script" <<SSDC_SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
CLAUDE_VERBOSE_DEPS=1 _ssdc_check_deps
SSDC_SCRIPT
  chmod +x "$script"
  run env PATH="$py_only" CLAUDE_VERBOSE_DEPS=1 bash "$script" 2>&1
  rm -f "$script"; rm -rf "$py_only"
  [ "$status" -eq 0 ]
  # When only 'python' resolves, show python+(python) not python+(python3)
  local hard_line; hard_line="$(echo "$output" | grep "hard:")"
  echo "$hard_line" | grep -q "python+(python)"
  if echo "$hard_line" | grep -q "python+(python3)"; then
    echo "FAIL: hard line showed python+(python3) but only 'python' was on PATH"
    return 1
  fi
}
