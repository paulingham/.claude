#!/usr/bin/env bash
# SessionStart dependency warner — sourced by session-start-bootstrap.sh.
# Sources the probe lib, prints STDERR warnings. ALWAYS returns 0 (never blocks).
# WHY: SessionStart cannot block (the hook has no enforcing mechanism); the
#      PreToolUse:Agent gate (harness-dependency-gate.sh) is the enforcing layer.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-dependency-check.sh" 2>/dev/null || return 0

_ssdc_check_deps() {
  _hdc_probe 2>/dev/null || true

  # WHY: verbose branch must come BEFORE the legacy warning block so the default
  # path (unset/!=1) is byte-for-byte unchanged.
  if [ "${CLAUDE_VERBOSE_DEPS:-}" = "1" ]; then
    _ssdc_print_verbose_report
    return 0
  fi

  if [ -n "${HDC_MISSING:-}" ]; then
    # WHY: sanitize before interpolating — defense-in-depth, symmetric with the gate's sanitization.
    local _ssdc_safe="${HDC_MISSING//[^a-z0-9 ]/_}"
    printf '[harness-dependency-check] MISSING REQUIRED: %s — install Git for Windows AND a Python interpreter, then add "env":{"CLAUDE_CODE_GIT_BASH_PATH":"C:\\Program Files\\Git\\bin\\bash.exe"} to settings.json. See knowledge/windows-setup.md.\n' \
      "$_ssdc_safe" >&2
  fi

  if [ -n "${HDC_SOFT_MISSING:-}" ]; then
    printf '[harness-dependency-check] OPTIONAL not found: flock (advisory — concurrency locking degrades gracefully; not required to run pipelines).\n' >&2
  fi

  return 0
}

_ssdc_print_verbose_report() {
  _hdc_feature_probe
  local _hard_line
  _hard_line="$(_ssdc_format_hard_line)"
  local _soft_line
  _soft_line="$(_ssdc_format_soft_line)"
  local _feature_line
  _feature_line="$(_ssdc_format_feature_line)"
  printf '[harness-deps] %s\n' "$_hard_line" >&2
  printf '[harness-deps] %s\n' "$_soft_line" >&2
  printf '[harness-deps] %s\n' "$_feature_line" >&2
  _ssdc_maybe_print_gates_line
}

_ssdc_format_hard_line() {
  local python_token
  if [ -n "${HDC_PYTHON:-}" ] && [ "${HDC_PYTHON}" != "python3" ]; then
    python_token="python+(${HDC_PYTHON})"
  elif [ -n "${HDC_PYTHON:-}" ]; then
    python_token="python+(python3)"
  else
    python_token="python-"
  fi
  local bash_mark git_mark realpath_mark mktemp_mark
  command -v bash    > /dev/null 2>&1 && bash_mark="bash+"    || bash_mark="bash-"
  command -v git     > /dev/null 2>&1 && git_mark="git+"      || git_mark="git-"
  command -v realpath > /dev/null 2>&1 && realpath_mark="realpath+" || realpath_mark="realpath-"
  command -v mktemp  > /dev/null 2>&1 && mktemp_mark="mktemp+" || mktemp_mark="mktemp-"
  printf 'hard: %s %s %s %s %s' \
    "$bash_mark" "$git_mark" "$python_token" "$realpath_mark" "$mktemp_mark"
}

_ssdc_format_soft_line() {
  local flock_mark
  command -v flock > /dev/null 2>&1 && flock_mark="flock+" || flock_mark="flock-"
  printf 'soft: %s' "$flock_mark"
}

_ssdc_format_feature_line() {
  local parts="" tool mark
  for tool in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    if command -v "$tool" > /dev/null 2>&1; then
      mark="${tool}+"
    else
      mark="${tool}-"
    fi
    parts="${parts:+$parts }$mark"
  done
  printf 'feature: %s' "$parts"
}

_ssdc_maybe_print_gates_line() {
  # WHY: emit gates: line ONLY when rtk or dippy is missing — keeps output <=4 lines.
  # Only rtk and dippy have real gate vars. CLAUDE_REQUIRE_PARRY and CLAUDE_REQUIRE_HCOM
  # do NOT exist — never print them.
  local rtk_missing=0 dippy_missing=0 gate_vars=""
  command -v rtk   > /dev/null 2>&1 || rtk_missing=1
  command -v dippy > /dev/null 2>&1 || dippy_missing=1
  [ "$rtk_missing"   -eq 1 ] && gate_vars="${gate_vars:+$gate_vars }CLAUDE_REQUIRE_RTK"
  [ "$dippy_missing" -eq 1 ] && gate_vars="${gate_vars:+$gate_vars }CLAUDE_REQUIRE_DIPPY"
  [ -n "$gate_vars" ] && printf '[harness-deps] gates: %s (set =1 to force install)\n' "$gate_vars" >&2 || true
}
