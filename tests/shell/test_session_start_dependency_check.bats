#!/usr/bin/env bats
# Verbose session-start dependency report — test suite.
bats_require_minimum_version 1.5.0
# AC1: report is unconditional — printed on every SessionStart (no env var required)
# AC2: plain-English format — Required / Optional / Tools groups (one line per missing tool)
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

@test "AC1-line-budget-all-present: fully-healthy hermetic box -> at most 3 lines" {
  # WHY: the compact-healthy-box guarantee only holds when ALL feature tools are present
  # (no "Tools missing:" lines, present-tools collapse to one line).
  # RED-ON-REVERT: if the report stops collapsing when all present, this fails.
  # HERMETIC: prepend a bin where ALL 7 feature tools + flock are stubbed, ahead of the
  # system PATH so command -v picks up the stubs regardless of host tool installation.
  # This is host-independent and CI-safe — CI runners don't have rtk/hcom/dippy/etc.
  local all_present_bin; all_present_bin="$(mktemp -d)"
  # flock: stub present
  ln -sf "$TRUE_BIN" "$all_present_bin/flock"
  # Stub ALL 7 feature tools present (overrides system absent tools)
  for t in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    ln -sf "$TRUE_BIN" "$all_present_bin/$t"
  done
  local script; script="$(mktemp /tmp/ssdc_budget_all.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1 | wc -l
SCRIPT
  chmod +x "$script"
  # WHY: prepend all_present_bin before system PATH so stubs take precedence.
  # bash is still found from system PATH — this is safe.
  run env PATH="$all_present_bin:$PATH" bash "$script"
  rm -f "$script"; rm -rf "$all_present_bin"
  [ "$status" -eq 0 ]
  local line_count="${output// /}"
  # Expected: 1 header + 1 Required all-present + 1 Tools present = 3 lines.
  # No Optional line (flock stubbed present), no Tools missing lines (all stubbed).
  [ "$line_count" -le 3 ]
}

@test "AC1-line-budget-worst-case: no feature tools present -> bounded at most 11 lines" {
  # WHY: documents the worst-case line budget honestly so CI never surprises us again.
  # Worst case: header(1) + Required(1) + Optional(1 — flock absent) +
  # 7 Tools missing lines = 10 lines. Cap at 11 for safety.
  # HERMETIC: use a no_features_bin that has NO feature tools and NO flock; prepend it
  # ahead of system PATH so it shadows any system-installed feature tools.
  local no_features_bin; no_features_bin="$(mktemp -d)"
  # Include all commands the scripts need, including wc for the pipeline.
  # WHY: use a PATH-only-no_features_bin so feature tools are provably absent.
  for cmd in bash git realpath mktemp python3 python jq dirname printf sed grep cat wc; do
    local resolved; resolved="$(command -v "$cmd" 2>/dev/null)"
    [ -n "$resolved" ] && ln -sf "$resolved" "$no_features_bin/$cmd" 2>/dev/null || true
  done
  # flock intentionally absent — triggers Optional line (worst-case path)
  # No feature tools — none added
  local script; script="$(mktemp /tmp/ssdc_budget_worst.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps 2>&1 | wc -l
SCRIPT
  chmod +x "$script"
  # WHY: use ONLY no_features_bin (no system PATH suffix) so feature tools are absent.
  # bash is resolved via absolute path — pass it explicitly to env.
  local real_bash; real_bash="$(command -v bash)"
  run env PATH="$no_features_bin" "$real_bash" "$script"
  rm -f "$script"; rm -rf "$no_features_bin"
  [ "$status" -eq 0 ]
  local line_count="${output// /}"
  # header(1) + Required(1) + Optional(1) + 7 Tools missing = 10 lines max.
  [ "$line_count" -le 11 ]
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

@test "AC2-tools-hcom-line: hcom missing -> own 'Tools missing: hcom' line with get.hcom.dev" {
  # RED-ON-REVERT: if hcom reverts to "re-run setup.sh" or is collapsed into a shared line, this fails.
  local no_tools; no_tools="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_hcom_install.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_tools" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_tools"
  [ "$status" -eq 0 ]
  # hcom is not on PATH on most boxes; must appear on its own line
  echo "$output" | grep "Tools missing: hcom" | grep -q "inter-agent messaging"
  echo "$output" | grep "Tools missing: hcom" | grep -q "get.hcom.dev"
}

@test "AC2-tools-parry-line: parry-guard missing -> own 'Tools missing: parry-guard' line with cargo install + rustup.rs" {
  # RED-ON-REVERT: if parry-guard's rustup.rs hint is removed, this fails.
  local no_tools; no_tools="$(_path_without rtk)"
  local script; script="$(mktemp /tmp/ssdc_parry_install.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_tools" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_tools"
  [ "$status" -eq 0 ]
  echo "$output" | grep "Tools missing: parry-guard" | grep -q "cargo install"
  echo "$output" | grep "Tools missing: parry-guard" | grep -q "rustup.rs"
}

@test "AC2-tools-pyright-line: pyright missing -> own 'Tools missing: pyright' line with npm install -g pyright" {
  local no_pyright; no_pyright="$(_path_without pyright)"
  local script; script="$(mktemp /tmp/ssdc_pyright_install.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$no_pyright" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$no_pyright"
  [ "$status" -eq 0 ]
  echo "$output" | grep "Tools missing: pyright" | grep -q "npm install -g pyright"
}

@test "AC2-tools-present-line: healthy box has 'Tools present:' line (not 'Tooling present:')" {
  # RED-ON-REVERT: if the label reverts to 'Tooling present:', this fails.
  local bin_with_all; bin_with_all="$(mktemp -d)"
  for f in "$FAKE_BIN"/*; do
    [ -e "$f" ] && ln -sf "$(readlink "$f" 2>/dev/null || echo "$f")" "$bin_with_all/$(basename "$f")" 2>/dev/null || true
  done
  for t in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    ln -sf "$TRUE_BIN" "$bin_with_all/$t"
  done
  local script; script="$(mktemp /tmp/ssdc_tools_present.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
_ssdc_check_deps
SCRIPT
  chmod +x "$script"
  run env PATH="$bin_with_all:$PATH" bash "$script" 2>&1
  rm -f "$script"; rm -rf "$bin_with_all"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "Tools present:"
  if echo "$output" | grep -q "Tooling present:"; then
    echo "FAIL: old 'Tooling present:' label appeared — should be 'Tools present:'"
    return 1
  fi
  # No 'Tools missing:' lines on a fully-healthy box
  if echo "$output" | grep -q "Tools missing:"; then
    echo "FAIL: 'Tools missing:' appeared on fully-healthy box"
    return 1
  fi
}

@test "AC2-tooling-gh-install: gh missing -> Tooling line contains cli.github.com, NOT 're-run setup.sh'" {
  # WHY: gh is NOT installed by setup.sh; it is an assumed prereq.
  # RED-ON-REVERT: if gh reverts to "re-run setup.sh", this fails.
  # WHY: _path_without gh removes gh from a constructed bin dir. We verify via
  # _ssdc_install_cmd directly (unit test) rather than a full integration PATH
  # trick because the Tooling summary line may also contain rtk/dippy missing
  # hints (which DO say "re-run setup.sh") on the same line, making a
  # grep-for-"gh"-then-grep-"re-run" check unreliable.
  local script; script="$(mktemp /tmp/ssdc_gh_install.XXXXXX.sh)"
  cat > "$script" <<SCRIPT
#!/usr/bin/env bash
. "$PROBE_LIB"
. "$WARNER_LIB"
# Unit-test the install cmd map directly: gh must point at cli.github.com
cmd="\$(_ssdc_install_cmd gh)"
echo "gh_cmd=\$cmd"
if echo "\$cmd" | grep -q "re-run setup.sh"; then
  echo "FAIL: gh install cmd said re-run setup.sh" >&2
  exit 1
fi
if ! echo "\$cmd" | grep -q "cli.github.com"; then
  echo "FAIL: gh install cmd missing cli.github.com" >&2
  exit 1
fi
SCRIPT
  chmod +x "$script"
  run env PATH="$FAKE_BIN:$PATH" bash "$script" 2>&1
  rm -f "$script"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "cli.github.com"
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

@test "AC2-gates-rtk-missing-line: rtk missing -> 'Tools missing: rtk' line contains CLAUDE_REQUIRE_RTK" {
  # RED-ON-REVERT: if rtk install hint is removed from its own missing line, this fails.
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
  # Hint must appear on the rtk-specific missing line
  echo "$output" | grep "Tools missing: rtk" | grep -q "CLAUDE_REQUIRE_RTK"
  if echo "$output" | grep -q "^\[harness-deps\] gates:"; then
    echo "FAIL: separate gates: line appeared — hint must be on Tools missing line"
    return 1
  fi
}

@test "M1-dippy-missing-line: dippy missing + rtk present -> 'Tools missing: dippy' line has CLAUDE_REQUIRE_DIPPY, no rtk line" {
  # WHY: M1 missing limb — mirrors AC2-gates-rtk-missing-line for dippy.
  # RED-ON-REVERT: if dippy install hint is removed from its own missing line, this fails.
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
  # dippy hint must appear on its own missing line
  echo "$output" | grep "Tools missing: dippy" | grep -q "CLAUDE_REQUIRE_DIPPY"
  # rtk is present — no "Tools missing: rtk" line should exist
  if echo "$output" | grep -q "Tools missing: rtk"; then
    echo "FAIL: 'Tools missing: rtk' appeared but rtk was present"
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
