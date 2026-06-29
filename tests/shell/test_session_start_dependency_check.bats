#!/usr/bin/env bats
# Verbose session-start dependency report — test suite.
bats_require_minimum_version 1.5.0
# AC1: report is unconditional — printed on every SessionStart (no env var required)
# AC2: plain-English format — Required / Optional / Tooling groups
# AC3: feature advisory — HDC_MISSING unaffected; feature tools never block
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

# ==============================================================================
# AC1 UNCONDITIONAL REPORT
# ==============================================================================

@test "AC1-always-on-healthy: no env var needed -> report always prints on healthy box" {
  # RED-ON-REVERT: if report becomes gated behind CLAUDE_VERBOSE_DEPS, this fails.
  local script; script="$(mktemp /tmp/ssdc_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  # Report must print even with no env var
  echo "$output" | grep -q "harness-deps"
  echo "$output" | grep -q "Required"
}

@test "AC1-stderr-only: report appears on stderr, not stdout" {
  local script; script="$(mktemp /tmp/ssdc_stderr_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
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
  echo "$stderr" | grep -q "Required"
}

@test "AC1-line-budget: healthy box report is at most 6 lines" {
  # WHY: compact report is important since it runs on every SessionStart.
  # Healthy box: 1 header + 1 Required all-present + 0 Optional (flock present, silent)
  # + 1 Tooling line = 3-4 lines. Cap at 6.
  local script; script="$(mktemp /tmp/ssdc_compact_test.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1 | wc -l
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script"
  rm -f "$script"
  [ "$status" -eq 0 ]
  local line_count="${output// /}"
  [ "$line_count" -le 6 ]
}

# ==============================================================================
# AC2 PLAIN-ENGLISH FORMAT
# ==============================================================================

@test "AC2-required-all-present: healthy box -> 'Required: all present' line with tool names" {
  local script; script="$(mktemp /tmp/ssdc_req_present.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "Required: all present"
  # Old shorthand must NOT appear
  if echo "$output" | grep -qE 'bash[+]|git[+]|python[+]'; then
    echo "FAIL: output still contains tool+ shorthand"
    return 1
  fi
}

@test "AC2-required-missing-loud: git missing -> loud 'Required MISSING: git' with windows-setup.md fix hint" {
  # RED-ON-REVERT: if the loud MISSING line is removed, this fails.
  local no_git; no_git="$(_path_without git)"
  local script; script="$(mktemp /tmp/ssdc_git_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_git" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "Required MISSING: git"
  echo "$output" | grep -q "knowledge/windows-setup.md"
}

@test "AC2-flock-missing-explained: flock absent -> 'flock missing' line with purpose text" {
  local no_flock; no_flock="$(_path_without flock)"
  local script; script="$(mktemp /tmp/ssdc_flock_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_flock" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_flock"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "flock missing"
  echo "$output" | grep -q "concurrent pipeline writes"
}

@test "AC2-tooling-purpose: tooling line contains purpose text for missing tools" {
  # Remove rtk from PATH so it shows as missing with purpose text.
  local no_rtk; no_rtk="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_tooling_purpose.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_rtk" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_rtk"
  [ "$status" -eq 0 ]
  # hcom is not on PATH on most boxes; its purpose must appear in missing summary
  echo "$output" | grep -q "inter-agent messaging"
}

@test "AC2-gates-no-fake-vars: report never contains CLAUDE_REQUIRE_PARRY or CLAUDE_REQUIRE_HCOM" {
  local script; script="$(mktemp /tmp/ssdc_no_fake_vars.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  if echo "$output" | grep -q "CLAUDE_REQUIRE_PARRY"; then
    echo "FAIL: output contained CLAUDE_REQUIRE_PARRY (no such gate var exists)"
    return 1
  fi
  if echo "$output" | grep -q "CLAUDE_REQUIRE_HCOM"; then
    echo "FAIL: output contained CLAUDE_REQUIRE_HCOM (no such gate var exists)"
    return 1
  fi
}

@test "AC2-no-separate-gates-line: report never has a standalone 'gates:' line" {
  # RED-ON-REVERT: if _ssdc_maybe_print_gates_line is re-added, this fails.
  # Gate-var hints now appear inline in the Tooling missing summary, not on a separate line.
  local script; script="$(mktemp /tmp/ssdc_no_gates_line.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  if echo "$output" | grep -q "^\[harness-deps\] gates:"; then
    echo "FAIL: standalone gates: line appeared — install hints must be inline in Tooling"
    return 1
  fi
}

@test "AC2-gates-rtk-missing-inline: rtk missing -> Tooling line contains CLAUDE_REQUIRE_RTK inline" {
  # RED-ON-REVERT: if rtk install hint is moved off the Tooling line, this fails.
  local bin_no_rtk; bin_no_rtk="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_gates_rtk_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_no_rtk" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_no_rtk"
  [ "$status" -eq 0 ]
  # Hint must appear in the Tooling line, not a separate gates: line
  echo "$output" | grep -i "Tooling" | grep -q "CLAUDE_REQUIRE_RTK"
  if echo "$output" | grep -q "^\[harness-deps\] gates:"; then
    echo "FAIL: separate gates: line appeared — hint must be inline in Tooling"
    return 1
  fi
}

@test "M1-dippy-missing-inline: dippy missing + rtk present -> Tooling line contains CLAUDE_REQUIRE_DIPPY, not CLAUDE_REQUIRE_RTK" {
  # WHY: M1 missing limb — mirrors AC2-gates-rtk-missing-inline for dippy.
  # RED-ON-REVERT: if dippy install hint is removed from the Tooling line, this fails.
  local bin_with_rtk_no_dippy; bin_with_rtk_no_dippy="$(_path_without dippy)"
  ln -sf "$TRUE_BIN" "$bin_with_rtk_no_dippy/rtk"
  local script; script="$(mktemp /tmp/ssdc_gates_dippy_missing.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_with_rtk_no_dippy" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_with_rtk_no_dippy"
  [ "$status" -eq 0 ]
  # dippy hint must appear inline in Tooling line
  echo "$output" | grep -i "Tooling" | grep -q "CLAUDE_REQUIRE_DIPPY"
  # rtk is present so its hint must NOT appear
  if echo "$output" | grep -i "Tooling" | grep -q "CLAUDE_REQUIRE_RTK"; then
    echo "FAIL: Tooling line named CLAUDE_REQUIRE_RTK but rtk was present"
    return 1
  fi
  # No separate gates: line
  if echo "$output" | grep -q "^\[harness-deps\] gates:"; then
    echo "FAIL: separate gates: line appeared"
    return 1
  fi
}

# ==============================================================================
# AC3 FEATURE ADVISORY — HDC_MISSING unaffected by feature probes
# ==============================================================================

@test "AC3-feature-advisory: feature tools absent do NOT add to HDC_MISSING" {
  # RED-ON-REVERT: if feature missing paths ever set HDC_MISSING, this fails.
  local script; script="$(mktemp /tmp/ssdc_feature_advisory.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_hdc_probe 2>/dev/null || true
_hdc_feature_probe
# HDC_MISSING must only name hard deps; never feature tools
echo "HDC_MISSING=|${HDC_MISSING:-}|"
SCRIPT
  chmod +x "$script"
  # Run with no feature tools on path
  local no_tools; no_tools="$(_path_without rtk)"
  run env PATH="$no_tools" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_tools"
  [ "$status" -eq 0 ]
  # HDC_MISSING must be empty (all hard deps are still present)
  echo "$output" | grep -q "HDC_MISSING=||"
}

@test "AC3-rc-zero-always: _ssdc_check_deps always returns 0 even with missing deps" {
  local no_git; no_git="$(_path_without git)"
  local script; script="$(mktemp /tmp/ssdc_rc.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_git" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_git"
  [ "$status" -eq 0 ]
}

@test "AC2-python-alias-display: when only 'python' resolves, Required line shows python not python3" {
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
  local true_bin; true_bin="$([ -x /usr/bin/true ] && echo /usr/bin/true || echo /bin/true)"
  ln -sf "$true_bin" "$py_only/flock" 2>/dev/null || true
  local real_py; real_py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
  [ -n "$real_py" ] && ln -sf "$real_py" "$py_only/python"
  local script; script="$(mktemp /tmp/ssdc_py_alias.XXXXXX.sh)"
  cat > "$script" <<SSDC_SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SSDC_SCRIPT
  chmod +x "$script"
  run env PATH="$py_only" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$py_only"
  [ "$status" -eq 0 ]
  # When only 'python' resolves, it should appear in the all-present summary
  echo "$output" | grep -q "Required: all present"
  echo "$output" | grep "Required" | grep -q "python"
}
