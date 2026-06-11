#!/usr/bin/env bash
# Auto-Learn Gate — Stop hook. Fires a context message telling the orchestrator
# to invoke /learn when thresholds are met. Never invokes /learn directly.
# Test override: CLAUDE_LEARN_TEST_HASH sets the learning/<hash> dir explicitly.
#
# enforces: protocols/autonomous-intelligence.md:Consolidation Gate
# protects: learn

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT    # set BEFORE any early exits so they get logged

check_bypass_gate "CLAUDE_DISABLE_AUTO_LEARN" && exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

LIB="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck source=_lib/project-hash.sh
source "$LIB/project-hash.sh"
# shellcheck source=_lib/learning-flock.sh
source "$LIB/learning-flock.sh"

INPUT=$(cat)  # capture Stop event JSON
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && { trap - EXIT; exit 0; }  # nested stop: pure no-op (no forensic write)
HASH="${CLAUDE_LEARN_TEST_HASH:-$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")}"
LD="$HARNESS_DATA/learning/$HASH"
STATE="$LD/.learn-state.json"; OBS="$LD/observations.jsonl"; LOG="$LD/.learn-gate.log"
mkdir -p "$LD"

if [[ ! -d "$LD/instincts" ]]; then
  printf '[auto-learn-gate] WARN instincts/ missing — bootstrap (fix #1) did not complete for project-hash=%s\n' "$HASH" >&2
  exit 0
fi

# Outer flock coordinates with learning-gc.sh; the module holds its own fcntl
# sidecar lock against re-entrant Stop firings within the same hook process.
with_learning_lock "$HASH" -- python3 "$LIB/auto_learn_gate.py" --state "$STATE" --obs "$OBS" --log "$LOG"
exit 0
