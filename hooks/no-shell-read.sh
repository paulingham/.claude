#!/usr/bin/env bash
# no-shell-read PreToolUse Bash hook.
# Blocks `tail`/`head`/`cat` clauses that target static files inside REPO_ROOT,
# forcing callers to use the Read tool. Allows streaming tail (-f/-F),
# outside-repo paths, and clauses with no path argument (pipe-only).
#
# enforces: rules/_detail/engineering-invariants.md:Code Shape
# protects: build-implementation

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

[[ "${CLAUDE_DISABLE_NO_SHELL_READ:-}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/no-shell-read-helpers.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

REPO_ROOT=$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null)
[[ -z "$REPO_ROOT" ]] && exit 0

OFFENDER=$(find_blocking_clause "$COMMAND" "$REPO_ROOT")
[[ -z "$OFFENDER" ]] && exit 0

printf 'Use the Read tool instead of %s for repo file paths.\n' "$OFFENDER" >&2
exit 2
