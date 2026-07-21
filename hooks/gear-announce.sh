#!/usr/bin/env bash
# gear-announce — UserPromptSubmit hook
#
# Surfaces the per-turn gear (PAIR/BUILD/PIPELINE) to the USER as a visible
# one-line systemMessage banner. gear-select.sh already classified the prompt
# and persisted the verdict to session state; today that verdict is only
# injected into the model's context, so the user never sees plainly which lane
# their prompt landed in. This hook reads that persisted verdict and echoes it
# back to the user — it NEVER re-classifies.
#
# ADVISORY: exits 0 in every case (an announce hook must never block a prompt),
# and stays SILENT whenever the gear is unconfirmable (state absent/unreadable,
# or an unexpected value). WHY fail-silent: if gear-select didn't run we would
# rather say nothing than announce a gear we cannot confirm.
#
# Must run AFTER gear-select in the UserPromptSubmit array so the gear-${sid}
# state key already exists when we read it — registered as the LAST entry.
#
# enforces: protocols/work-class-routing.md
# protects: gear-visibility, user-feedback

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "UserPromptSubmit"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/state-dir.sh"
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/session-id.sh"

INPUT=$(cat)
sid=$(resolve_session_id "$INPUT")

gear=$(_state_read "gear-${sid}" 2>/dev/null) || { trap - EXIT; exit 0; }
gear="${gear//$'\n'/}"

case "$gear" in
  PAIR)     HINT="fast interactive lane, no heavy pipeline" ;;
  BUILD)    HINT="standard pipeline (plan → build → review → gate → ship)" ;;
  PIPELINE) HINT="max-rigour pipeline (plan validation, tournament build)" ;;
  *)        trap - EXIT; exit 0 ;;  # empty or unexpected -> confirm nothing, say nothing
esac

printf '{"systemMessage": "GEAR: %s — %s"}\n' "$gear" "$HINT"
exit 0
