#!/usr/bin/env bash
# spec-blind-write-guard PreToolUse hook (Write|Edit).
#
# Allows the spec-blind-validator to Write/Edit ONLY under test directories
# (tests/, test/, spec/, __tests__/) anchored to the repo root (SEC-HIGH-2).
# Read-allowlist files (interface.ts, package.json, README.md, etc.) are
# READ-ONLY for this validator — the write-allowlist is strictly tighter.
#
# For every other subagent, fast-exits 0. AC17-style early-exit branch
# (grep -F over raw stdin BEFORE jq) ensures no overhead on the no-op path.
#
# Symlink-bypass mitigation (SEC-HIGH-1): the path is realpath-resolved BEFORE
# allowlist matching so a symlink under tests/ that points to src/internal.ts
# cannot be written-through.
#
# IF SPEC-BLIND WRITES ARE LEAKING: check the .subagent_type top-level JSON
# field is present in stdin. The fallback chain in _spec_blind_parse_input
# also tolerates CLAUDE_SUBAGENT_TYPE env-var resolution (SEC-MED-2).
# IF WRITES ARE OVER-BLOCKING legitimate test paths: check the directory
# globs in hooks/_lib/spec-blind-allow-paths.sh::is_path_allowed_for_spec_blind_write.
#
# enforces: rules/_detail/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator" \
   && [[ "${CLAUDE_SUBAGENT_TYPE:-}" != "spec-blind-validator" ]]; then
  exit 0
fi

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Write|Edit"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-guard-common.sh"
# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-path.sh"
_spec_blind_parse_input

[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
case "$TOOL_NAME" in
  Write|Edit) ;;
  *) exit 0 ;;
esac

[[ -z "$FILE_PATH" ]] && exit 0

case "$FILE_PATH" in
  /*) ABS_PATH="$FILE_PATH" ;;
  *)  ABS_PATH="$(pwd)/$FILE_PATH" ;;
esac

# SEC-HIGH-1: realpath-resolve BEFORE allowlist match.
ABS_REAL="$(_spec_blind_realpath "$ABS_PATH")"
[[ -z "$ABS_REAL" ]] && ABS_REAL="$ABS_PATH"

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/spec-blind-allow-paths.sh"

if is_path_allowed_for_spec_blind_write "$ABS_REAL"; then
  exit 0
fi

_spec_blind_log_violation "write-guard" "$TOOL_NAME" "$FILE_PATH"

echo "BLOCKED: spec-blind-validator may not write $FILE_PATH. Allowed write targets: <repo-root>/{tests,test,spec,__tests__}/**." >&2
exit 2
