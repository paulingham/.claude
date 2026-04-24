#!/usr/bin/env bash
# Background worker for eval-capture. Contamination + oracle filters + case write.
# Invoked as: bash eval-capture-worker.sh <pr-number>
# CWD is the repo root. The test hook (CLAUDE_EVAL_CAPTURE_NOFORK=1) runs synchronously;
# production hook forks this via nohup & disown.
set -u

HERE_ECW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE_ECW/eval-capture-worker-core.sh"

eval_capture_worker "${1:-}"
