#!/usr/bin/env bash
# spec-blind-read-guard PreToolUse hook (Read|Grep|Glob).
#
# Blocks the spec-blind-validator from reading paths outside the public-surface
# allowlist (hooks/_lib/spec-blind-allow-paths.txt). For every other subagent,
# fast-exits 0 — AC17 budgets < 25ms median for this no-op path.
#
# IF SPEC-BLIND READS ARE LEAKING: check the .subagent_type top-level JSON field
# is present in stdin (verified at hooks/planning-agent-edit-scope.sh:24,
# hooks/cost-feed.sh:33). The fallback chain in _spec_blind_parse_input also
# tolerates CLAUDE_SUBAGENT_TYPE env-var resolution (SEC-MED-2).
# IF READS ARE OVER-BLOCKING: check the path matrix in
# tests/shell/test_spec_blind_read_guard.bats — and the pattern list in
# hooks/_lib/spec-blind-allow-paths.txt.
#
# Symlink-bypass mitigation (SEC-HIGH-1): the path is realpath-resolved BEFORE
# allowlist matching so a symlink at
# `pipeline-state/{task-id}/plan.md -> src/internal.ts` cannot slip through.
#
# enforces: protocols/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)
# protects: spec-blind-validate

set -uo pipefail

# AC17 fast-exit: read raw stdin once, fast-substring-test for the subagent
# token BEFORE invoking jq. False positive here is fast non-block — the JSON
# parse below confirms exact match before any deny decision. Note: the
# fast-path triggers on the literal token regardless of source (JSON field or
# env-var fallback), so SEC-MED-2 fail-open is closed even on the fast path
# when the orchestrator passes CLAUDE_SUBAGENT_TYPE in the spawn env.
INPUT=$(cat)
if ! printf '%s' "$INPUT" | grep -F -q "spec-blind-validator" \
   && [[ "${CLAUDE_SUBAGENT_TYPE:-}" != "spec-blind-validator" ]]; then
  exit 0
fi

# Lazy-load logging only when we know we'll potentially block.
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Read|Grep|Glob"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/spec-blind-guard-common.sh"
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/spec-blind-path.sh"
_spec_blind_parse_input

# Exact-match comparison — substring "spec-blind-validator-v2" would not match here.
[[ "$SUBAGENT_TYPE" != "spec-blind-validator" ]] && exit 0
case "$TOOL_NAME" in
  Read|Grep|Glob) ;;
  *) exit 0 ;;
esac

# No path → nothing to check (e.g. Glob with default cwd) — let it through.
[[ -z "$FILE_PATH" ]] && exit 0

# Resolve relative paths against pwd so absolute-prefix patterns can match.
case "$FILE_PATH" in
  /*) ABS_PATH="$FILE_PATH" ;;
  *)  ABS_PATH="$(pwd)/$FILE_PATH" ;;
esac

# SEC-HIGH-1: realpath-resolve BEFORE allowlist match. A symlink at an
# allowlisted path that points OUTSIDE the allowlist would otherwise pass.
# Empty result means python3 is unavailable or the path doesn't exist —
# fall back to the literal absolute path; the allowlist check is then no
# weaker than the legacy behaviour, but the deny-list path closure for
# realpath-resolvable symlinks is preserved.
ABS_REAL="$(_spec_blind_realpath "$ABS_PATH")"
[[ -z "$ABS_REAL" ]] && ABS_REAL="$ABS_PATH"

# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/spec-blind-allow-paths.sh"

if is_path_allowed_for_spec_blind "$ABS_REAL"; then
  exit 0
fi

_spec_blind_log_violation "read-guard" "$TOOL_NAME" "$FILE_PATH"

echo "BLOCKED: spec-blind-validator may not read $FILE_PATH. See skills/spec-blind-validate/SKILL.md § Public API Surface." >&2
exit 2
