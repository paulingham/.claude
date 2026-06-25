#!/usr/bin/env bash
# harness-dependency-gate — PreToolUse:Agent hook.
# Fails closed when harness runtime prerequisites (bash, python, git, realpath,
# mktemp) are absent. Blocks Agent spawns with exit 2 until resolved.
# Soft deps (flock) are advisory only — never block.
#
# enforces: rules/core.md:Iron Law 8
# protects: pipeline runtime prerequisites
# if-broken-look-at: hooks/_lib/harness-dependency-check.sh (_hdc_probe; HDC_MISSING=hard/block, HDC_SOFT_MISSING=advisory); set CLAUDE_DISABLE_DEPENDENCY_GATE=1 to unblock; knowledge/windows-setup.md

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# WHY: single inline function avoids repeating the unevaluable block message (DRY).
_hdg_block_unevaluable() {
  printf 'BLOCKED: harness prerequisites could not be verified (dependency probe unavailable). Refusing to proceed (Iron Law 8). Look at hooks/_lib/harness-dependency-check.sh; set CLAUDE_DISABLE_DEPENDENCY_GATE=1 to override.\n' >&2
}

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" 2>/dev/null || { _hdg_block_unevaluable; exit 2; }
# WHY: guard existence before calling — undefined function → || exit 0 fires (fail-open). Symmetric with _hdc_probe guard below.
declare -F check_hook_profile > /dev/null || { _hdg_block_unevaluable; exit 2; }
check_hook_profile "minimal" || exit 0

INPUT=$(cat)
# WHY: pure-bash tool_name parse — jq is NOT a guaranteed dep; using it here would create
# the very class of fail-open it is designed to catch. Non-Agent / unparseable → exit 0
# matches the harness convention at main-branch-guard.sh:30-33.
[[ "$INPUT" =~ \"tool_name\"[[:space:]]*:[[:space:]]*\"([^\"]*)\" ]] && TOOL_NAME="${BASH_REMATCH[1]}" || TOOL_NAME=""
[ "$TOOL_NAME" = "Agent" ] || exit 0

if [ "${CLAUDE_DISABLE_DEPENDENCY_GATE:-}" = "1" ]; then
  printf 'harness-dependency-gate bypassed via CLAUDE_DISABLE_DEPENDENCY_GATE=1\n' >&2
  exit 0
fi

# Source probe lib — fail closed if unavailable (Iron Law 8).
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/harness-dependency-check.sh" 2>/dev/null || { _hdg_block_unevaluable; exit 2; }

# Verify _hdc_probe is defined — fail closed if source silently failed (Iron Law 8).
declare -F _hdc_probe > /dev/null || { _hdg_block_unevaluable; exit 2; }

_hdc_probe

# INV-3: use +x set-test to distinguish HDC_MISSING never-set (→deny) from set-but-empty (→allow).
if [[ -z "${HDC_MISSING+x}" ]]; then
  _hdg_block_unevaluable
  exit 2
fi

if [ -n "$HDC_MISSING" ]; then
  # INV-4: sanitize before interpolating into the block message.
  safe="${HDC_MISSING//[^a-z0-9 ]/_}"
  printf 'BLOCKED: harness prerequisites missing: %s. Pipeline work is refused until installed (or set CLAUDE_DISABLE_DEPENDENCY_GATE=1 to override). See knowledge/windows-setup.md.\n' \
    "$safe" >&2
  exit 2
fi

exit 0
