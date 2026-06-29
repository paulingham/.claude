#!/usr/bin/env bash
# SessionStart dependency warner — sourced by session-start-bootstrap.sh.
# Sources the probe lib, prints a plain-English dependency report to STDERR.
# ALWAYS returns 0 (never blocks).
# WHY: SessionStart cannot block (the hook has no enforcing mechanism); the
#      PreToolUse:Agent gate (harness-dependency-gate.sh) is the enforcing layer.
# WHY: report is unconditional — printed on every SessionStart so engineers always
#      know what is present/missing without needing a special env var.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-dependency-check.sh" 2>/dev/null || return 0

_ssdc_check_deps() {
  _hdc_probe 2>/dev/null || true
  _hdc_feature_probe
  _ssdc_print_english_report
  return 0
}

# ---------------------------------------------------------------------------
# Plain-English report — always printed, compact (~3-4 lines on healthy box)
# ---------------------------------------------------------------------------

# Purpose strings for every dep — keyed presentation data, not probe logic.
_ssdc_purpose() {
  case "$1" in
    bash)                      echo "shell the hooks run under" ;;
    git)                       echo "version control & worktrees" ;;
    python)                    echo "runs hook & helper scripts" ;;
    realpath)                  echo "resolves absolute paths for hooks" ;;
    mktemp)                    echo "creates temp files for hooks" ;;
    flock)                     echo "locks concurrent pipeline writes (advisory; macOS lacks it, safe to ignore)" ;;
    rtk)                       echo "token-saving CLI output proxy" ;;
    gh)                        echo "GitHub CLI (used by Ship/Deploy)" ;;
    hcom)                      echo "inter-agent messaging" ;;
    dippy)                     echo "session observability" ;;
    parry-guard)               echo "ML injection detection" ;;
    typescript-language-server) echo "TypeScript/JavaScript language server" ;;
    pyright)                   echo "Python language server" ;;
    *)                         echo "harness dependency" ;;
  esac
}

# Fix hint for a missing dep (only rtk and dippy have gate vars).
_ssdc_fix_hint() {
  case "$1" in
    git)     echo "Fix: install Git (Windows: see knowledge/windows-setup.md), then restart the session." ;;
    python)  echo "Fix: install Python 3, then restart the session." ;;
    rtk)     echo "install: set CLAUDE_REQUIRE_RTK=1, re-run setup.sh" ;;
    dippy)   echo "install: set CLAUDE_REQUIRE_DIPPY=1, re-run setup.sh" ;;
    *)       echo "re-run setup.sh" ;;
  esac
}

_ssdc_print_english_report() {
  printf '[harness-deps] Dependency check\n' >&2
  _ssdc_report_required
  _ssdc_report_optional
  _ssdc_report_tooling
}

_ssdc_report_required() {
  # Hard deps in canonical order; python displayed via HDC_PYTHON alias.
  local -a hard_deps=(bash git python realpath mktemp)
  local -a missing_deps=()
  local -a present_names=()

  local dep display
  for dep in "${hard_deps[@]}"; do
    if [ "$dep" = "python" ]; then
      if [ -z "${HDC_PYTHON:-}" ]; then
        missing_deps+=("$dep")
      else
        present_names+=("${HDC_PYTHON}")
      fi
    else
      if echo " ${HDC_MISSING:-} " | grep -q " ${dep} "; then
        missing_deps+=("$dep")
      else
        present_names+=("$dep")
      fi
    fi
  done

  if [ "${#missing_deps[@]}" -eq 0 ]; then
    local names_csv; names_csv="$(printf '%s, ' "${present_names[@]}")"
    names_csv="${names_csv%, }"
    printf '[harness-deps] Required: all present (%s).\n' "$names_csv" >&2
  else
    if [ "${#present_names[@]}" -gt 0 ]; then
      local names_csv; names_csv="$(printf '%s, ' "${present_names[@]}")"
      names_csv="${names_csv%, }"
      printf '[harness-deps] Required present: %s.\n' "$names_csv" >&2
    fi
    local mdep purpose hint
    for mdep in "${missing_deps[@]}"; do
      purpose="$(_ssdc_purpose "$mdep")"
      hint="$(_ssdc_fix_hint "$mdep")"
      # WHY: sanitize missing dep name before interpolation — defense-in-depth.
      local _safe="${mdep//[^a-z0-9 ]/_}"
      printf '[harness-deps] Required MISSING: %s - %s. %s\n' "$_safe" "$purpose" "$hint" >&2
    done
  fi
}

_ssdc_report_optional() {
  local purpose; purpose="$(_ssdc_purpose flock)"
  if [ -n "${HDC_SOFT_MISSING:-}" ]; then
    printf '[harness-deps] Optional: flock missing - %s.\n' "$purpose" >&2
  fi
  # flock present: omit for compactness
}

_ssdc_report_tooling() {
  # HDC_FEATURE_PRESENT / HDC_FEATURE_MISSING set by _hdc_feature_probe (called before us).
  local present_list="${HDC_FEATURE_PRESENT:-}"
  local missing_list="${HDC_FEATURE_MISSING:-}"

  # Build comma-separated present names
  local present_csv=""
  if [ -n "$present_list" ]; then
    present_csv="${present_list// /, }"
  fi

  # Build missing summary with inline purpose and fix hint.
  # WHY: rtk and dippy have real gate vars; _ssdc_fix_hint returns the install line for them
  # and "re-run setup.sh" for others — reused here to keep hint strings DRY (one place).
  # NEVER print CLAUDE_REQUIRE_PARRY or CLAUDE_REQUIRE_HCOM — those gate vars do not exist.
  local missing_summary="" tool purpose hint
  for tool in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    if echo " ${missing_list} " | grep -q " ${tool} "; then
      purpose="$(_ssdc_purpose "$tool")"
      hint="$(_ssdc_fix_hint "$tool")"
      missing_summary="${missing_summary}${tool} (${purpose} - ${hint}); "
    fi
  done
  missing_summary="${missing_summary%; }"

  if [ -n "$present_csv" ] && [ -n "$missing_summary" ]; then
    printf '[harness-deps] Tooling present: %s. Missing: %s.\n' "$present_csv" "$missing_summary" >&2
  elif [ -n "$present_csv" ]; then
    printf '[harness-deps] Tooling: all present (%s).\n' "$present_csv" >&2
  elif [ -n "$missing_summary" ]; then
    printf '[harness-deps] Tooling: none present. Missing: %s.\n' "$missing_summary" >&2
  fi
}
