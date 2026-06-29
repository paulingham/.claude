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

# Grounded install commands per tool — one place, no duplication.
# WHY: flock returns "" (advisory; macOS lacks it, safe to ignore — no install step).
# WHY: CLAUDE_REQUIRE_PARRY and CLAUDE_REQUIRE_HCOM do NOT exist — never printed here;
#      hcom and parry-guard have real install commands instead.
_ssdc_install_cmd() {
  case "$1" in
    rtk)                        echo "set CLAUDE_REQUIRE_RTK=1 and re-run setup.sh" ;;
    dippy)                      echo "set CLAUDE_REQUIRE_DIPPY=1 and re-run setup.sh" ;;
    hcom)                       echo "curl -fsSL https://get.hcom.dev | sh   (or npm i -g hcom)" ;;
    parry-guard)                echo "cargo install --git https://github.com/vaporif/parry --features candle --no-default-features   (requires Rust; see https://rustup.rs)" ;;
    pyright)                    echo "npm install -g pyright" ;;
    typescript-language-server) echo "npm install -g typescript-language-server" ;;
    gh)                         echo "brew install gh   (or see https://cli.github.com)" ;;
    git)                        echo "install Git (Windows: see knowledge/windows-setup.md), then restart the session" ;;
    python)                     echo "install Python 3, then restart the session" ;;
    flock)                      echo "" ;;
    *)                          echo "" ;;
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
    local mdep purpose cmd
    for mdep in "${missing_deps[@]}"; do
      purpose="$(_ssdc_purpose "$mdep")"
      cmd="$(_ssdc_install_cmd "$mdep")"
      # WHY: sanitize missing dep name before interpolation — defense-in-depth.
      local _safe="${mdep//[^a-z0-9 ]/_}"
      printf '[harness-deps] Required MISSING: %s - %s. Install: %s\n' "$_safe" "$purpose" "$cmd" >&2
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

  # Present tools: collapse to one line (healthy box stays ~3 lines total).
  if [ -n "$present_list" ]; then
    local present_csv; present_csv="${present_list// /, }"
    printf '[harness-deps] Tools present: %s.\n' "$present_csv" >&2
  fi

  # Missing tools: one line each with purpose + grounded install command.
  # WHY: _ssdc_install_cmd is the single source for install text (DRY).
  # NEVER print CLAUDE_REQUIRE_PARRY or CLAUDE_REQUIRE_HCOM — those gate vars do not exist;
  # hcom and parry-guard have real install commands in _ssdc_install_cmd instead.
  local tool purpose cmd
  for tool in rtk gh hcom dippy parry-guard typescript-language-server pyright; do
    if echo " ${missing_list} " | grep -q " ${tool} "; then
      purpose="$(_ssdc_purpose "$tool")"
      cmd="$(_ssdc_install_cmd "$tool")"
      printf '[harness-deps] Tools missing: %s - %s. Install: %s\n' "$tool" "$purpose" "$cmd" >&2
    fi
  done
}
