#!/usr/bin/env bash
# Learning GC — SessionStart. Archives old observations.jsonl entries and
# VACUUMs memory.sqlite. Runs at most once every 30 days per project hash.
# Escape hatch: CLAUDE_DISABLE_LEARNING_GC=1. Never blocks session start.

set -uo pipefail

[[ "${CLAUDE_DISABLE_LEARNING_GC:-0}" == "1" ]] && exit 0

LIB_DIR="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck disable=SC1091
source "${LIB_DIR}/project-hash.sh"

HASH=$(_project_hash --fallback "local")
PROJECT_DIR="$HOME/.claude/learning/$HASH"
DB_PATH="$HOME/.claude/db/memory.sqlite"
RETENTION="${CLAUDE_LEARNING_RETENTION_DAYS:-90}"

[[ -d "$PROJECT_DIR" ]] || exit 0

python3 "${LIB_DIR}/learning_gc_runner.py" \
  "$PROJECT_DIR" "$RETENTION" "$DB_PATH" 2>&1 || true

exit 0
