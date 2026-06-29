#!/usr/bin/env bash
# Harness dependency probe — sourced by the SessionStart warner and the
# PreToolUse:Agent gate. Sources NOTHING (no harness-paths.sh, no log.sh).
# Safe under set -u. Detection via `command -v` only — NO python execution.
#
# After sourcing, call _hdc_probe. Sets (never exports):
#   HDC_MISSING      — space-separated HARD deps that are absent (blocks pipeline)
#   HDC_SOFT_MISSING — space-separated SOFT deps that are absent (advisory only)
#   HDC_PYTHON       — the resolving interpreter name (python3 / python / py) or ""
# Returns 0 iff HDC_MISSING is empty; non-zero otherwise.
#
# HARD deps (absent => block): bash git realpath mktemp + one python interpreter
# SOFT deps (absent => warn, never block): flock

_hdc_probe() {
  HDC_MISSING=""
  HDC_SOFT_MISSING=""
  HDC_PYTHON=""

  _hdc_require bash
  _hdc_require git
  _hdc_require realpath
  _hdc_require mktemp
  _hdc_probe_python
  _hdc_soft_check flock

  [ -z "$HDC_MISSING" ]
}

_hdc_require() {
  local cmd="$1"
  command -v "$cmd" > /dev/null 2>&1 && return 0
  HDC_MISSING="${HDC_MISSING:+$HDC_MISSING }$cmd"
}

_hdc_probe_python() {
  local interp
  for interp in python3 python py; do
    if command -v "$interp" > /dev/null 2>&1; then
      HDC_PYTHON="$interp"
      return
    fi
  done
  HDC_MISSING="${HDC_MISSING:+$HDC_MISSING }python"
}

_hdc_soft_check() {
  local cmd="$1"
  command -v "$cmd" > /dev/null 2>&1 && return 0
  HDC_SOFT_MISSING="${HDC_SOFT_MISSING:+$HDC_SOFT_MISSING }$cmd"
}

# _hdc_feature_probe — advisory feature-tool detection. Sets two NEW vars:
#   HDC_FEATURE_PRESENT — space-separated names of tools found
#   HDC_FEATURE_MISSING — space-separated names of tools absent
# Feature absence is ADVISORY: never touches HDC_MISSING, never affects _hdc_probe's return.
# Detection via `command -v` ONLY (no python, no jq, no sourcing anything).
# WHY: parry-guard and hcom have no gate var (CLAUDE_REQUIRE_PARRY / CLAUDE_REQUIRE_HCOM
#      do NOT exist) — only rtk and dippy have real gate enforcement vars.
_hdc_feature_probe() {
  HDC_FEATURE_PRESENT=""
  HDC_FEATURE_MISSING=""
  local tool
  for tool in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    if command -v "$tool" > /dev/null 2>&1; then
      HDC_FEATURE_PRESENT="${HDC_FEATURE_PRESENT:+$HDC_FEATURE_PRESENT }$tool"
    else
      HDC_FEATURE_MISSING="${HDC_FEATURE_MISSING:+$HDC_FEATURE_MISSING }$tool"
    fi
  done
}
