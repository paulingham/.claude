#!/usr/bin/env bash
# Auto-capture eval case on harness PR merge.
# Trigger: PostToolUse matcher=Bash where tool_input.command starts with "gh pr merge".
# Privacy gate: committed marker eval/.privacy-acked OR env CLAUDE_EVAL_CAPTURE_ACKED=1.
# Detached: hook exits <1s; worker runs in background (nohup & disown) unless
#           CLAUDE_EVAL_CAPTURE_NOFORK=1 (test hook) runs worker synchronously.
# Writes candidates to eval/cases/.candidates/ ONLY — never promotes.
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -u

HERE_ECM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE_ECM/_lib/eval-capture-dispatch.sh"

eval_capture_dispatch
