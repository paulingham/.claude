#!/usr/bin/env bash
# root-snapshot-capture — SessionStart hook.
#
# Captures a snapshot of `git status --porcelain` for the root working tree
# at session start. This snapshot is later compared by root-tree-clean-check.sh
# (Stop + SessionEnd) to detect root-tree contamination caused by concurrent
# agents running mutation/verification tooling at REPO_ROOT.
#
# State location: $HARNESS_DATA/root-snapshots/<session_id>.txt
# NEVER writes under REPO_ROOT — runtime state belongs in HARNESS_DATA.
#
# enforces: CLAUDE.md § Runtime State Location (worktree isolation)
# protects: root working tree integrity across concurrent sessions
# references: forensics-instinct-injector-edit.md Anomaly 2
# if-broken-look-at: $HARNESS_DATA/root-snapshots/<session>.txt

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# log.sh sourced from deployed location; fails open when not available (e.g. test env)
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh" 2>/dev/null || {
    _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
}
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# Require git repo (no-op if not in a git repo)
git rev-parse --git-dir > /dev/null 2>&1 || exit 0

# Session ID (sanitized)
SESSION_ID="${CLAUDE_SESSION_ID:-local-$$}"
SESSION_ID="${SESSION_ID//[^A-Za-z0-9_.-]/}"
[[ -z "$SESSION_ID" ]] && SESSION_ID="local-$$"

# Snapshot dir under HARNESS_DATA (never under REPO_ROOT)
SNAP_DIR="$HARNESS_DATA/root-snapshots"
mkdir -p "$SNAP_DIR" 2>/dev/null || exit 0

SNAP_FILE="$SNAP_DIR/${SESSION_ID}.txt"

# Capture git status --porcelain from repo root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

{
    printf '# root-snapshot: session=%s ts=%s repo=%s\n' \
        "$SESSION_ID" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$REPO_ROOT"
    git -C "$REPO_ROOT" status --porcelain 2>/dev/null
} > "$SNAP_FILE" 2>/dev/null

exit 0
