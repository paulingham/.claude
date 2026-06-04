#!/usr/bin/env bash
# root-tree-clean-check — Stop + SessionEnd hook.
#
# Asserts root working-tree cleanliness against the session-start snapshot
# captured by root-snapshot-capture.sh (SessionStart).
#
# On drift:
#   - Emits a LOUD warning naming the drifted files to stderr
#   - Preserves a timestamped diff under $HARNESS_DATA/forensics/root-drift-<ts>.diff
#   - Does NOT auto-revert (forensics only — never destructive)
#   - Always exits 0 (advisory — does not block session end)
#
# When clean: silent and cheap (single git status call, string compare).
# When no snapshot exists (first session): silent exit 0.
#
# enforces: CLAUDE.md § Runtime State Location (worktree isolation)
# protects: root working tree integrity across concurrent sessions
# references: forensics-instinct-injector-edit.md Anomaly 2
# if-broken-look-at: $HARNESS_DATA/root-snapshots/<session>.txt
#                    $HARNESS_DATA/forensics/root-drift-*.diff

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# log.sh is sourced from the deployed location; fails open (not available in test envs)
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh" 2>/dev/null || {
    _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
}
_log_hook_start
_log_hook_trigger "Stop:SessionEnd"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# Require git repo
git rev-parse --git-dir > /dev/null 2>&1 || exit 0

# Session ID (sanitized)
SESSION_ID="${CLAUDE_SESSION_ID:-local-$$}"
SESSION_ID="${SESSION_ID//[^A-Za-z0-9_.-]/}"
[[ -z "$SESSION_ID" ]] && SESSION_ID="local-$$"

SNAP_DIR="$HARNESS_DATA/root-snapshots"
SNAP_FILE="$SNAP_DIR/${SESSION_ID}.txt"

# No snapshot: first session or snapshot missing — silent exit
[[ -f "$SNAP_FILE" ]] || exit 0

# Current root status
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
CURRENT_STATUS=$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)

# Baseline from snapshot (strip comment lines)
BASELINE=$(grep -v '^#' "$SNAP_FILE" 2>/dev/null)

# Fast-path: identical -> clean, silent
if [[ "$CURRENT_STATUS" == "$BASELINE" ]]; then
    exit 0
fi

# Drift detected — compute what changed relative to baseline
TIMESTAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
FORENSICS_DIR="$HARNESS_DATA/forensics"
mkdir -p "$FORENSICS_DIR" 2>/dev/null || true
FORENSICS_FILE="$FORENSICS_DIR/root-drift-${TIMESTAMP}.diff"

# Build diff between baseline and current status (not a git diff — just the porcelain delta)
{
    printf '# root-tree contamination detected\n'
    printf '# session: %s\n' "$SESSION_ID"
    printf '# timestamp: %s\n' "$TIMESTAMP"
    printf '# repo: %s\n' "$REPO_ROOT"
    printf '\n--- baseline (session-start snapshot)\n'
    printf '%s\n' "${BASELINE:-(empty — repo was clean at session start)}"
    printf '\n+++ current (session-end)\n'
    printf '%s\n' "${CURRENT_STATUS:-(empty — repo is now clean)}"
    printf '\n--- git diff --stat (head)\n'
    git -C "$REPO_ROOT" diff --stat HEAD 2>/dev/null || true
    printf '\n--- git diff (unified, first 200 lines)\n'
    git -C "$REPO_ROOT" diff HEAD 2>/dev/null | head -200 || true
} > "$FORENSICS_FILE" 2>/dev/null

# Extract the drifted file names for the warning message
DRIFTED_FILES=$(printf '%s\n' "$CURRENT_STATUS" | awk '{print $2}' | tr '\n' ' ')
# Files in current but not in baseline (new dirt)
NEW_DIRTY=$(comm -13 \
    <(printf '%s\n' "$BASELINE" | sort 2>/dev/null) \
    <(printf '%s\n' "$CURRENT_STATUS" | sort 2>/dev/null) 2>/dev/null \
    | awk '{print $2}' | tr '\n' ' ')
[[ -n "$NEW_DIRTY" ]] && DRIFTED_FILES="$NEW_DIRTY"

cat >&2 <<EOF

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
[root-tree-clean-check] WARNING: ROOT TREE CONTAMINATION DETECTED
  Session         : $SESSION_ID
  Repo root       : $REPO_ROOT
  Drifted files   : ${DRIFTED_FILES:-<see diff below>}
  Forensics diff  : $FORENSICS_FILE

  Current git status --porcelain:
$(printf '%s\n' "$CURRENT_STATUS" | sed 's/^/    /')

  The root working tree has uncommitted changes that were NOT present at session
  start. This is the exact failure class from the 2026-06-03 instinct_injector
  incident. Review the forensics diff and investigate which agent or session
  introduced these changes.

  DO NOT auto-revert — preserve the evidence for forensics.
  Diff preserved at: $FORENSICS_FILE
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

EOF

# Always exit 0 — this is advisory/forensics only, never blocks session end
exit 0
