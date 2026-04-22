#!/usr/bin/env bash
# setup.sh — Bootstrap script for fresh ~/.claude/ installs
# Idempotent: safe to run multiple times. Continues on failure.
# Usage: bash ~/.claude/setup.sh

set -uo pipefail

# Source the bootstrap libs: detect-os.sh provides the canonical OS identifier,
# dippy-gate.sh decides whether dippy + claude-devtools install based on
# (OS, CLAUDE_REQUIRE_DIPPY). Both libs ship in this tree; their absence is a
# packaging bug, so fail fast with a clear diagnostic rather than falling
# through to undefined functions (which would silently skip on every OS,
# contradicting the Mac-only default).
_SETUP_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$_SETUP_DIR/scripts/_lib/detect-os.sh" || {
  printf 'FATAL: cannot source %s/scripts/_lib/detect-os.sh\n' "$_SETUP_DIR" >&2
  exit 1
}
# shellcheck disable=SC1091
source "$_SETUP_DIR/scripts/_lib/dippy-gate.sh" || {
  printf 'FATAL: cannot source %s/scripts/_lib/dippy-gate.sh\n' "$_SETUP_DIR" >&2
  exit 1
}
# --- end bootstrap ---

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

INSTALLED=()
SKIPPED=()
FAILED=()

print_success() { printf "${GREEN}  %s${RESET}\n" "$1"; }
print_failure() { printf "${RED}  %s${RESET}\n" "$1"; }
print_warning() { printf "${YELLOW}  %s${RESET}\n" "$1"; }
print_header()  { printf "\n${BLUE}%s${RESET}\n" "$1"; }

record_installed() { INSTALLED+=("$1"); print_success "$1"; }
record_skipped()  { SKIPPED+=("$1");  print_warning "$1 (already installed)"; }
record_failed()   { FAILED+=("$1");   print_failure "$1"; }

command_exists() { command -v "$1" > /dev/null 2>&1; }

print_header "=== Claude Code Orchestration Layer Setup ==="
echo ""

# -------------------------------------------------------------------
# Step 1: Check prerequisites
# -------------------------------------------------------------------
print_header "Step 1: Checking prerequisites"

PREREQS_OK=true

if command_exists node; then
  print_success "node $(node --version)"
else
  print_failure "node not found -- install Node.js first"
  PREREQS_OK=false
fi

if command_exists npm; then
  print_success "npm $(npm --version)"
else
  print_failure "npm not found -- install Node.js first"
  PREREQS_OK=false
fi

case "$(uname -s)" in
    Darwin)
        if command_exists brew; then
            print_success "brew $(brew --version | head -1)"
        else
            print_failure "brew not found -- install Homebrew: https://brew.sh"
            PREREQS_OK=false
        fi
        ;;
    Linux)
        print_success "Linux detected -- skipping brew check"
        ;;
esac

if [[ "$PREREQS_OK" == "false" ]]; then
  print_failure "Prerequisites missing. Install them and re-run this script."
  exit 1
fi

# -------------------------------------------------------------------
# Step 2: Install external tools
# -------------------------------------------------------------------
print_header "Step 2: Installing external tools"

# -- Dippy + claude-devtools (Mac-only by default; gated by CLAUDE_REQUIRE_DIPPY) --
# CLAUDE_REQUIRE_DIPPY=1 forces install on any OS (opt-in on Linux).
# CLAUDE_REQUIRE_DIPPY=0 forces skip on any OS (opt-out on macOS).
# Unset: macOS installs, Linux skips.
_SETUP_OS="$(detect_os)"

if should_install_dippy "$_SETUP_OS"; then
  echo ""
  echo "  Dippy (AST-based bash command safety)..."
  if command_exists dippy; then
    record_skipped "dippy"
  else
    if brew tap ldayton/dippy 2>/dev/null && brew install dippy 2>/dev/null; then
      record_installed "dippy"
    else
      record_failed "dippy (brew tap ldayton/dippy && brew install dippy)"
    fi
  fi

  echo ""
  echo "  claude-devtools (session observability)..."
  if brew list --cask claude-devtools > /dev/null 2>&1; then
    record_skipped "claude-devtools"
  else
    if brew install --cask claude-devtools 2>/dev/null; then
      record_installed "claude-devtools"
    else
      record_failed "claude-devtools (brew install --cask claude-devtools)"
    fi
  fi
else
  print_warning "dippy + claude-devtools: skipped — $(dippy_skip_reason "$_SETUP_OS")"
  SKIPPED+=("dippy (gated)")
  SKIPPED+=("claude-devtools (gated)")
fi

# -- Rust toolchain --
echo ""
echo "  Rust toolchain..."
if command_exists rustup; then
  record_skipped "rust toolchain"
elif command_exists cargo; then
  record_skipped "rust toolchain (cargo found, no rustup)"
else
  if curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y 2>/dev/null; then
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env" 2>/dev/null || true
    record_installed "rust toolchain"
  else
    record_failed "rust toolchain (rustup installer)"
  fi
fi

# -- parry-guard (ML injection detection — candle backend, pure Rust) --
echo ""
echo "  parry-guard (ML injection detection — candle backend, pure Rust)..."
if command_exists parry-guard || [[ -x "$HOME/.cargo/bin/parry-guard" ]]; then
  record_skipped "parry-guard"
else
  if command_exists cargo; then
    if cargo install --git https://github.com/vaporif/parry --features candle --no-default-features 2>/dev/null; then
      record_installed "parry-guard"
    else
      record_failed "parry-guard (cargo install --git https://github.com/vaporif/parry --features candle --no-default-features)"
    fi
  else
    record_failed "parry-guard (cargo not found -- install Rust first)"
  fi
fi

# Set up HF token for ML model download
if [[ ! -f "$HOME/.parry-guard/.hf-token" ]]; then
    mkdir -p "$HOME/.parry-guard"
    if [[ -f "$HOME/.cache/huggingface/token" ]]; then
        cp "$HOME/.cache/huggingface/token" "$HOME/.parry-guard/.hf-token"
        chmod 600 "$HOME/.parry-guard/.hf-token"
        print_success "Copied HF token from huggingface cache"
    elif [[ -n "${HF_TOKEN:-}" ]]; then
        echo -n "$HF_TOKEN" > "$HOME/.parry-guard/.hf-token"
        chmod 600 "$HOME/.parry-guard/.hf-token"
        print_success "Wrote HF token from environment"
    else
        print_warning "parry-guard ML requires a HuggingFace token"
        print_warning "  1. Get a free token at: huggingface.co/settings/tokens (READ scope)"
        print_warning "  2. Accept model terms at: huggingface.co/ProtectAI/deberta-v3-small-prompt-injection-v2"
        print_warning "  3. Run: echo 'YOUR_TOKEN' > ~/.parry-guard/.hf-token && chmod 600 ~/.parry-guard/.hf-token"
    fi
fi

# -- hcom (inter-agent communication) --
echo ""
echo "  hcom (inter-agent communication)..."
if [[ -x "$HOME/.local/bin/hcom" ]]; then
  record_skipped "hcom"
elif command_exists hcom; then
  record_skipped "hcom"
else
  if curl -fsSL https://get.hcom.dev | sh 2>/dev/null; then
    record_installed "hcom"
  else
    if npm install -g hcom 2>/dev/null; then
      record_installed "hcom (via npm)"
    else
      record_failed "hcom (tried official installer and npm)"
    fi
  fi
fi

# -------------------------------------------------------------------
# Step 3: Trail of Bits plugins
# -------------------------------------------------------------------
print_header "Step 3: Trail of Bits security plugins"

if ! command_exists claude; then
  print_failure "claude CLI not found -- install Claude Code first"
  record_failed "trail-of-bits-plugins (claude CLI not found)"
else
  echo ""
  echo "  Adding Trail of Bits marketplace..."
  if claude plugin marketplace add trailofbits/skills 2>/dev/null; then
    print_success "Trail of Bits marketplace added"
  else
    print_warning "Trail of Bits marketplace add returned non-zero (may already exist)"
  fi

  PLUGINS=(
    "supply-chain-risk-auditor"
    "variant-analysis"
    "differential-review"
    "sharp-edges"
    "static-analysis"
  )

  for plugin in "${PLUGINS[@]}"; do
    echo ""
    echo "  Installing ${plugin}..."
    if claude plugin install "${plugin}@trailofbits" 2>/dev/null; then
      record_installed "plugin: ${plugin}"
    else
      # Non-zero exit may mean already installed
      print_warning "plugin: ${plugin} (install returned non-zero -- may already exist)"
      SKIPPED+=("plugin: ${plugin}")
    fi
  done
fi

# -------------------------------------------------------------------
# Step 4: Create required directories
# -------------------------------------------------------------------
print_header "Step 4: Creating required directories"

CLAUDE_DIR="$HOME/.claude"

create_directory() {
  local dir_path="$1"
  local label="$2"
  if [[ -d "$dir_path" ]]; then
    record_skipped "directory: ${label}"
  else
    if mkdir -p "$dir_path"; then
      record_installed "directory: ${label}"
    else
      record_failed "directory: ${label}"
    fi
  fi
}

create_directory "${CLAUDE_DIR}/metrics" "metrics/"
create_directory "${CLAUDE_DIR}/learning/instincts" "learning/instincts/"
# claude-mem Story 1: SQLite index + embedding model dirs
create_directory "${CLAUDE_DIR}/db" "db/"
create_directory "${CLAUDE_DIR}/models" "models/"

# -------------------------------------------------------------------
# Step 5: Verify hooks are executable
# -------------------------------------------------------------------
print_header "Step 5: Verifying hooks are executable"

HOOKS_DIR="${CLAUDE_DIR}/hooks"
HOOKS_FIXED=0

if [[ -d "$HOOKS_DIR" ]]; then
  for hook_file in "${HOOKS_DIR}"/*.sh; do
    if [[ -f "$hook_file" && ! -x "$hook_file" ]]; then
      chmod +x "$hook_file"
      HOOKS_FIXED=$(( HOOKS_FIXED + 1 ))
    fi
  done

  HOOK_COUNT=$(find "$HOOKS_DIR" -maxdepth 1 -name '*.sh' -type f | wc -l | tr -d ' ')

  if [[ "$HOOKS_FIXED" -gt 0 ]]; then
    record_installed "hooks: fixed ${HOOKS_FIXED} of ${HOOK_COUNT} scripts"
  else
    print_success "hooks: all ${HOOK_COUNT} scripts already executable"
    SKIPPED+=("hooks: all executable")
  fi
else
  record_failed "hooks directory not found at ${HOOKS_DIR}"
fi

# -------------------------------------------------------------------
# Step 6: Validate settings.json
# -------------------------------------------------------------------
print_header "Step 6: Validating settings.json"

SETTINGS_FILE="${CLAUDE_DIR}/settings.json"

if [[ -f "$SETTINGS_FILE" ]]; then
  if python3 -m json.tool "$SETTINGS_FILE" > /dev/null 2>&1; then
    record_installed "settings.json: valid JSON"
  else
    record_failed "settings.json: invalid JSON -- run: python3 -m json.tool ${SETTINGS_FILE}"
  fi
else
  record_failed "settings.json not found at ${SETTINGS_FILE}"
fi

# -------------------------------------------------------------------
# Step 6b: Fix machine-specific paths in settings.json
# -------------------------------------------------------------------
print_header "Step 6b: Fix machine-specific paths in settings.json"

# Note: ORT_DYLIB_PATH in settings.json points to /opt/homebrew/lib/libonnxruntime.dylib (Mac path).
# On Linux, parry-guard ML inference will degrade gracefully (warning logged, falls back to no-op).
# A follow-up may make this fully dynamic if settings.json gains per-platform env support.

if [[ -f "$SETTINGS_FILE" ]]; then
  PATHS_FIXED=0

  # Fix hcom path to current machine (macOS /Users/ and Linux /home/)
  if grep -qE "/(Users|home)/[^/]*/\.local/bin/hcom" "$SETTINGS_FILE" 2>/dev/null; then
    sed -i.bak "s|/Users/[^/]*/\.local/bin/hcom|${HOME}/.local/bin/hcom|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    sed -i.bak "s|/home/[^/]*/\.local/bin/hcom|${HOME}/.local/bin/hcom|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    print_success "Fixed hcom paths to ${HOME}/.local/bin/hcom"
    PATHS_FIXED=$(( PATHS_FIXED + 1 ))
  fi

  # Fix parry-guard HF token path (macOS /Users/ and Linux /home/)
  if grep -qE "/(Users|home)/[^/]*/\.config/parry-guard" "$SETTINGS_FILE" 2>/dev/null; then
    sed -i.bak "s|/Users/[^/]*/\.config/parry-guard|${HOME}/.config/parry-guard|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    sed -i.bak "s|/home/[^/]*/\.config/parry-guard|${HOME}/.config/parry-guard|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    print_success "Fixed parry-guard token path to ${HOME}/.config/parry-guard"
    PATHS_FIXED=$(( PATHS_FIXED + 1 ))
  fi

  # Fix parry-guard binary path (macOS /Users/ and Linux /home/)
  if grep -qE "/(Users|home)/[^/]*/\.cargo/bin/parry-guard" "$SETTINGS_FILE" 2>/dev/null; then
    sed -i.bak "s|/Users/[^/]*/\.cargo/bin/parry-guard|${HOME}/.cargo/bin/parry-guard|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    sed -i.bak "s|/home/[^/]*/\.cargo/bin/parry-guard|${HOME}/.cargo/bin/parry-guard|g" "$SETTINGS_FILE"
    rm -f "${SETTINGS_FILE}.bak"
    print_success "Fixed parry-guard binary path to ${HOME}/.cargo/bin/parry-guard"
    PATHS_FIXED=$(( PATHS_FIXED + 1 ))
  fi

  # Validate JSON is still valid after sed replacements
  if python3 -m json.tool < "$SETTINGS_FILE" > /dev/null 2>&1; then
    if [[ "$PATHS_FIXED" -gt 0 ]]; then
      record_installed "settings.json: ${PATHS_FIXED} path pattern(s) fixed for this machine"
    else
      print_success "settings.json: no machine-specific paths needed fixing"
      SKIPPED+=("settings.json: paths already correct")
    fi
  else
    record_failed "settings.json: path replacement broke JSON"
  fi
else
  print_warning "settings.json not found -- skipping path fix"
fi

# -------------------------------------------------------------------
# Step 7: Run agnix if available
# -------------------------------------------------------------------
print_header "Step 7: Running agnix configuration linter"

if command_exists npx; then
  echo ""
  echo "  Running: npx agnix ${CLAUDE_DIR}/"
  if npx agnix "${CLAUDE_DIR}/" 2>/dev/null; then
    record_installed "agnix: lint passed"
  else
    print_warning "agnix: lint completed with warnings or not available"
    SKIPPED+=("agnix: may not be published yet")
  fi
else
  record_failed "agnix: npx not found"
fi

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
print_header "=== Setup Summary ==="

echo ""
if [[ ${#INSTALLED[@]} -gt 0 ]]; then
  printf "${GREEN}Installed/Configured (%d):${RESET}\n" "${#INSTALLED[@]}"
  for item in "${INSTALLED[@]}"; do
    printf "  ${GREEN}  %s${RESET}\n" "$item"
  done
fi

echo ""
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  printf "${YELLOW}Already Present (%d):${RESET}\n" "${#SKIPPED[@]}"
  for item in "${SKIPPED[@]}"; do
    printf "  ${YELLOW}  %s${RESET}\n" "$item"
  done
fi

echo ""
if [[ ${#FAILED[@]} -gt 0 ]]; then
  printf "${RED}Failed (%d):${RESET}\n" "${#FAILED[@]}"
  for item in "${FAILED[@]}"; do
    printf "  ${RED}  %s${RESET}\n" "$item"
  done
  echo ""
  print_failure "Some installations failed. Review the errors above and retry manually."
  exit 1
fi

echo ""
print_success "All setup steps completed successfully."
exit 0
