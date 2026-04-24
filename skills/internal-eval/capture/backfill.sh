#!/usr/bin/env bash
# /internal-eval capture backfill [--limit N] [--since YYYY-MM-DD]
# Scans merged PRs, filters via oracle-paths.json, writes candidates.
set -u
CAPTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CAPTURE_DIR/lib/privacy.sh"
source "$CAPTURE_DIR/lib/oracle-match.sh"
source "$CAPTURE_DIR/lib/gh-pr-to-case.sh"
source "$CAPTURE_DIR/lib/backfill-run.sh"

LIMIT=30; SINCE="2026-01-01"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --limit) LIMIT="$2"; shift 2 ;;
    --since) SINCE="$2"; shift 2 ;;
    *) echo "backfill.sh: unknown arg: $1" >&2; exit 2 ;;
  esac
done

privacy_gate
backfill_run "$LIMIT" "$SINCE" "$CAPTURE_DIR"
