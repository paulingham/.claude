#!/usr/bin/env bash
# Background worker for eval-capture. Contamination filter + oracle filter + case write.
# Invoked as: bash eval-capture-worker.sh <pr-number>
# CWD is expected to be the repo root (same as the hook).
set -u

mkdir -p eval/runs/.capture-log
: > "eval/runs/.capture-log/worker-invoked.marker"

exit 0
