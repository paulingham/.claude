#!/usr/bin/env bash
# Trace Cleanup Hook — SessionStart.
#
# Prunes prompt traces older than 7 days from ~/.claude/metrics/*/trace/.
# No-op when metrics dir does not exist (common — tracing is opt-in).
# Never blocks session start.

set -uo pipefail

METRICS_DIR="${HOME}/.claude/metrics"
[[ -d "$METRICS_DIR" ]] || exit 0

# Prune files older than 7 days inside any session's trace/ subdir.
find "$METRICS_DIR" -mindepth 3 -maxdepth 3 -type f -path '*/trace/*' -mtime +7 -delete 2>/dev/null || true

# Remove now-empty trace/ dirs, then empty session dirs.
find "$METRICS_DIR" -mindepth 2 -maxdepth 2 -type d -name trace -empty -delete 2>/dev/null || true
find "$METRICS_DIR" -mindepth 1 -maxdepth 1 -type d -empty -delete 2>/dev/null || true

exit 0
