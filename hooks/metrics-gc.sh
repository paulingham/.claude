#!/usr/bin/env bash
# Metrics GC — SessionStart. Prunes the metrics/ directory so SessionStart
# hooks that scale O(metrics-dir count) (session-start-bootstrap.sh,
# hook-self-test.sh, trace-cleanup.sh) stay fast.
#
#   - Test-fixture session dirs (test-*, rg-*, bats-*) are removed unconditionally.
#   - Real local-* session dirs older than CLAUDE_METRICS_RETENTION_DAYS are removed.
#   - Stale subagent-runtimes/*.start files older than CLAUDE_SUBAGENT_MAX_RUNTIME
#     are removed so runtime-guard.sh does not trip on dead state.
#
# Rate-limited via a JSON sentinel at metrics/.gc-state.json
# ({"last_run": <epoch_seconds>}).
# Escape hatch: CLAUDE_DISABLE_METRICS_GC=1 → fast-exit 0.
# Always exits 0 — never blocks SessionStart.
#
# enforces: rules/_detail/agent-protocol.md:Resource Bounds
# protects: pipeline, all-skills

# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

set -uo pipefail

[[ "${CLAUDE_DISABLE_METRICS_GC:-0}" == "1" ]] && exit 0

METRICS_DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}"
[[ -d "$METRICS_DIR" ]] || exit 0

INTERVAL_HOURS="${CLAUDE_METRICS_GC_INTERVAL_HOURS:-24}"
RETENTION_DAYS="${CLAUDE_METRICS_RETENTION_DAYS:-7}"
START_FILE_MAX_AGE="${CLAUDE_SUBAGENT_MAX_RUNTIME:-1800}"
SENTINEL="$METRICS_DIR/.gc-state.json"

# Rate limit: only run if interval has elapsed since last_run.
if [[ "$INTERVAL_HOURS" != "0" && -f "$SENTINEL" ]]; then
  now_epoch="$(date +%s)"
  last_run="$(python3 -c '
import json, sys
try:
    print(int(json.load(open(sys.argv[1])).get("last_run", 0)))
except Exception:
    print(0)
' "$SENTINEL" 2>/dev/null || echo 0)"
  interval_seconds=$(( INTERVAL_HOURS * 3600 ))
  if (( now_epoch - last_run < interval_seconds )); then
    exit 0
  fi
fi

PRUNED=0

# 1. Test fixture dirs — pruned unconditionally regardless of mtime.
#    Patterns from the spec: test-*, test-cap-*, test-fm-*, test-valid-*,
#    rg-*, bats-*. Use find -maxdepth 1 to avoid traversing into them.
for prefix in 'test-*' 'rg-*' 'bats-*'; do
  while IFS= read -r -d '' dir; do
    rm -rf -- "$dir" && PRUNED=$(( PRUNED + 1 ))
  done < <(find "$METRICS_DIR" -mindepth 1 -maxdepth 1 -type d -name "$prefix" -print0 2>/dev/null)
done

# 2. Real session dirs (local-*) older than RETENTION_DAYS — prune.
#    -mtime +N is "strictly more than N*24h ago"; use the documented retention.
while IFS= read -r -d '' dir; do
  rm -rf -- "$dir" && PRUNED=$(( PRUNED + 1 ))
done < <(find "$METRICS_DIR" -mindepth 1 -maxdepth 1 -type d -name 'local-*' -mtime "+${RETENTION_DAYS}" -print0 2>/dev/null)

# 3. Stale subagent-runtimes/*.start files (older than START_FILE_MAX_AGE seconds).
#    runtime-guard.sh global-scans these on every Bash|Write|Edit call, so dead
#    state needs to be cleared so it does not trip false positives.
STALE_START_COUNT=0
while IFS= read -r -d '' f; do
  rm -f -- "$f" && STALE_START_COUNT=$(( STALE_START_COUNT + 1 ))
done < <(
  find "$METRICS_DIR" -mindepth 3 -maxdepth 3 -type f \
       -path '*/subagent-runtimes/*.start' \
       -mmin "+$(( START_FILE_MAX_AGE / 60 ))" -print0 2>/dev/null
)
PRUNED=$(( PRUNED + STALE_START_COUNT ))

# Update sentinel — JSON written via python3 (per spec, never echo > file.json).
python3 - "$SENTINEL" <<'PY'
import json, os, sys, time
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as fh:
    json.dump({"last_run": int(time.time())}, fh)
PY

if (( PRUNED > 0 )); then
  echo "metrics-gc: pruned $PRUNED entries from $METRICS_DIR" >&2
fi

exit 0
