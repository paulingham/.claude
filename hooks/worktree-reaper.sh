#!/usr/bin/env bash
# Worktree Reaper — SessionStart. Reaps ONLY provably-safe orphaned worktrees
# under .claude/worktrees/, reports the rest, and warns when total size exceeds
# a cap. Fixes recurring orphaned-worktree disk bloat without ever destroying
# unshipped work.
#
# SAFETY CONTRACT — a worktree is removed ONLY when ALL THREE hold:
#   (a) its branch is merged into main (git branch --merged main lists it);
#   (b) zero uncommitted AND zero untracked changes (git status --porcelain empty);
#   (c) zero commits ahead of main (rev-list --count main..<branch> == 0).
# If ANY fails the worktree is RETAINED and reported. Removal uses a plain
# `git worktree remove` (NO --force) so even a logic slip cannot destroy content.
#
# Rate-limited via metrics/.worktree-reaper-state.json ({"last_run": <epoch>}).
# Escape hatch: CLAUDE_DISABLE_WORKTREE_REAPER=1 → fast-exit 0.
# Size guard: total du -sm vs CLAUDE_WORKTREE_SIZE_CAP_MB (default 2048).
# Always exits 0 — never blocks SessionStart.
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline, all-skills

# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/check-bypass-gate.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

set -uo pipefail

check_bypass_gate "CLAUDE_DISABLE_WORKTREE_REAPER" && exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
WORKTREES_DIR="$REPO_ROOT/.claude/worktrees"
[[ -d "$WORKTREES_DIR" ]] || exit 0

INTERVAL_HOURS="${CLAUDE_WORKTREE_REAPER_INTERVAL_HOURS:-24}"
SIZE_CAP_MB="${CLAUDE_WORKTREE_SIZE_CAP_MB:-2048}"
SENTINEL="$HARNESS_DATA/metrics/.worktree-reaper-state.json"

# Rate limit: only run if the interval has elapsed since last_run (0 = always).
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

# Size guard — emit the warning at the TOP of output, before any reaping.
TOTAL_MB="$(du -sm "$WORKTREES_DIR" 2>/dev/null | awk '{print $1}')"
TOTAL_MB="${TOTAL_MB:-0}"
if (( TOTAL_MB > SIZE_CAP_MB )); then
  echo "worktree-reaper: WARNING — .claude/worktrees/ size ${TOTAL_MB}MB exceeds cap ${SIZE_CAP_MB}MB. Reaping safe worktrees; retained ones below hold unshipped work." >&2
fi

# Branches merged into main (trimmed names, current-branch marker stripped).
MERGED_BRANCHES="$(git -C "$REPO_ROOT" branch --merged main 2>/dev/null | sed 's/^[* +]*//')"

is_merged() {
  grep -qxF "$1" <<< "$MERGED_BRANCHES"
}

REAPED=0
RETAINED=0

# Enumerate worktree paths; keep only those under .claude/worktrees/, never REPO_ROOT.
while IFS= read -r path; do
  [[ "$path" == "$WORKTREES_DIR/"* ]] || continue
  [[ "$path" == "$REPO_ROOT" ]] && continue
  [[ -d "$path" ]] || continue

  branch="$(git -C "$path" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  dirty_count="$(git -C "$path" status --porcelain 2>/dev/null | grep -c .)"
  ahead="$(git -C "$REPO_ROOT" rev-list --count "main..$branch" 2>/dev/null || echo 1)"
  merged="no"; is_merged "$branch" && merged="yes"
  size="$(du -sh "$path" 2>/dev/null | awk '{print $1}')"

  if [[ "$merged" == "yes" && "$dirty_count" -eq 0 && "$ahead" -eq 0 ]]; then
    if git -C "$REPO_ROOT" worktree remove "$path" 2>/dev/null; then
      REAPED=$(( REAPED + 1 ))
      continue
    fi
  fi
  RETAINED=$(( RETAINED + 1 ))
  echo "worktree-reaper: RETAINED $path (branch=$branch ahead=$ahead dirty=$dirty_count merged=$merged size=$size)" >&2
done < <(git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')

# Update sentinel — JSON written via python3 (never echo > file.json).
python3 - "$SENTINEL" <<'PY'
import json, os, sys, time
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as fh:
    json.dump({"last_run": int(time.time())}, fh)
PY

echo "worktree-reaper: reaped $REAPED safe worktree(s), $RETAINED retained (unshipped work)" >&2

exit 0
