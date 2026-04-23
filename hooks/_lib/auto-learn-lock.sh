#!/usr/bin/env bash
# Portable lock helpers for auto-learn-gate. mkdir-based lock (works on macOS/Linux).

_all_acquire() {
  local lockdir="$1" max="${2:-25}" i=0
  while ! mkdir "$lockdir" 2>/dev/null; do
    i=$(( i + 1 )); [[ "$i" -ge "$max" ]] && return 1
    sleep 0.2
  done
}

_all_release() {
  local lockdir="$1"
  [[ -d "$lockdir" ]] && rmdir "$lockdir" 2>/dev/null || true
}
