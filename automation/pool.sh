#!/usr/bin/env bash
# pool.sh -- Worktree pool management for Jira automation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log() {
  local level="$1"
  shift
  echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] [$level] $*" >&2
}

# ---------------------------------------------------------------------------
# pool_init -- Create pool directory and worktree slots
# Returns: 0 success, 1 not a git repo, 2 worktree creation failed
# ---------------------------------------------------------------------------
pool_init() {
  if [ ! -d "$REPO_PATH/.git" ]; then
    _log ERROR "REPO_PATH ($REPO_PATH) is not a git repository"
    return 1
  fi

  local gitignore_path="$REPO_PATH/.gitignore"
  if [ ! -f "$gitignore_path" ] || ! grep -qxF '.tickets/' "$gitignore_path"; then
    echo '.tickets/' >> "$gitignore_path"
    _log INFO "Added .tickets/ to .gitignore"
  fi

  mkdir -p "$POOL_DIR"

  local slot_index=1
  while [ "$slot_index" -le "$POOL_SIZE" ]; do
    local slot_name="slot-$slot_index"
    if ! git -C "$REPO_PATH" worktree list | grep -q "$slot_name"; then
      if ! git -C "$REPO_PATH" worktree add "$POOL_DIR/$slot_name" --detach; then
        _log ERROR "Failed to create worktree $slot_name"
        return 2
      fi
      _log INFO "Created worktree $slot_name"
    else
      _log INFO "Worktree $slot_name already exists"
    fi
    slot_index=$((slot_index + 1))
  done

  _log INFO "Pool initialized with $POOL_SIZE slots"
  return 0
}

# ---------------------------------------------------------------------------
# pool_claim -- Atomically claim a free slot for a ticket
# Args: ticket_key
# Stdout: slot path on success
# Returns: 0 claimed, 3 no slot available
# ---------------------------------------------------------------------------
pool_claim() {
  local ticket_key="$1"

  local slot_index=1
  while [ "$slot_index" -le "$POOL_SIZE" ]; do
    local slot_path="$POOL_DIR/slot-$slot_index"
    local lock_dir="$slot_path/.slot-lock.d"

    if mkdir "$lock_dir" 2>/dev/null; then
      echo "$$" > "$lock_dir/pid"
      echo "$ticket_key" > "$lock_dir/ticket"
      date '+%Y-%m-%dT%H:%M:%S%z' > "$lock_dir/claimed_at"
      _log INFO "Claimed slot-$slot_index for $ticket_key (PID $$)"
      echo "$slot_path"
      return 0
    fi

    local owner_pid
    owner_pid="$(cat "$lock_dir/pid" 2>/dev/null || echo "")"
    if [ -n "$owner_pid" ] && ! kill -0 "$owner_pid" 2>/dev/null; then
      _log WARN "Stale lock in slot-$slot_index (PID $owner_pid dead), removing"
      rm -rf "$lock_dir"
    fi

    slot_index=$((slot_index + 1))
  done

  _log WARN "No free slots available (pool size: $POOL_SIZE)"
  return 3
}

# ---------------------------------------------------------------------------
# pool_release -- Release a claimed slot and clean up
# Args: slot_path
# Returns: 0 success, 1 cleanup failed
# ---------------------------------------------------------------------------
pool_release() {
  local slot_path="$1"
  local lock_dir="$slot_path/.slot-lock.d"

  _clean_orphan_worktrees

  git -C "$REPO_PATH" worktree prune 2>/dev/null || true

  if ! (cd "$slot_path" && git checkout --detach HEAD 2>/dev/null && git clean -fdx && git reset --hard HEAD); then
    _log ERROR "Failed to clean slot at $slot_path"
    return 1
  fi

  _clean_pipeline_state "$lock_dir"
  rm -rf "$lock_dir"

  _log INFO "Released slot at $slot_path"
  return 0
}

# ---------------------------------------------------------------------------
# _clean_orphan_worktrees -- Remove agent worktrees left behind
# ---------------------------------------------------------------------------
_clean_orphan_worktrees() {
  local worktree_path
  git -C "$REPO_PATH" worktree list --porcelain | grep '^worktree ' | while read -r _ worktree_path; do
    case "$worktree_path" in
      */.claude/worktrees/*|*/worktree-*)
        _log INFO "Removing orphan worktree: $worktree_path"
        git -C "$REPO_PATH" worktree remove --force "$worktree_path" 2>/dev/null || true
        ;;
    esac
  done
}

# ---------------------------------------------------------------------------
# _clean_pipeline_state -- Remove pipeline state files for a ticket
# Args: lock_dir
# ---------------------------------------------------------------------------
_clean_pipeline_state() {
  local lock_dir="$1"
  local ticket_key
  ticket_key="$(cat "$lock_dir/ticket" 2>/dev/null || echo "")"

  if [ -n "$ticket_key" ]; then
    local state_dir="$HARNESS_DATA/pipeline-state"
    if [ -d "$state_dir" ]; then
      find "$state_dir" -name "${ticket_key}*" -delete 2>/dev/null || true
      _log INFO "Cleaned pipeline state for $ticket_key"
    fi
  fi
}

# ---------------------------------------------------------------------------
# pool_reset_slot -- Reset a slot to latest origin/main
# Args: slot_path
# Returns: 0 success, 1 fetch failed, 2 checkout failed
# ---------------------------------------------------------------------------
pool_reset_slot() {
  local slot_path="$1"

  if ! git -C "$slot_path" fetch origin main; then
    _log ERROR "Failed to fetch origin/main in $slot_path"
    return 1
  fi

  if ! (cd "$slot_path" && git checkout --detach origin/main && git clean -fdx); then
    _log ERROR "Failed to checkout origin/main in $slot_path"
    return 2
  fi

  _log INFO "Reset slot at $slot_path to origin/main"
  return 0
}

# ---------------------------------------------------------------------------
# pool_status -- Print status of all pool slots
# ---------------------------------------------------------------------------
pool_status() {
  local in_use=0
  local slot_index=1

  while [ "$slot_index" -le "$POOL_SIZE" ]; do
    local slot_path="$POOL_DIR/slot-$slot_index"
    local lock_dir="$slot_path/.slot-lock.d"

    if [ -d "$lock_dir" ]; then
      local ticket pid claimed_at alive_status
      ticket="$(cat "$lock_dir/ticket" 2>/dev/null || echo "unknown")"
      pid="$(cat "$lock_dir/pid" 2>/dev/null || echo "unknown")"
      claimed_at="$(cat "$lock_dir/claimed_at" 2>/dev/null || echo "unknown")"

      if [ "$pid" != "unknown" ] && kill -0 "$pid" 2>/dev/null; then
        alive_status="alive"
      else
        alive_status="dead"
      fi

      echo "slot-$slot_index: CLAIMED | ticket=$ticket | pid=$pid ($alive_status) | since=$claimed_at"
      in_use=$((in_use + 1))
    else
      echo "slot-$slot_index: IDLE"
    fi

    slot_index=$((slot_index + 1))
  done

  echo "---"
  echo "Summary: $in_use/$POOL_SIZE in use"
}

# ---------------------------------------------------------------------------
# pool_recover -- Reclaim slots with dead owner processes
# ---------------------------------------------------------------------------
pool_recover() {
  local recovered=0
  local slot_index=1

  while [ "$slot_index" -le "$POOL_SIZE" ]; do
    local slot_path="$POOL_DIR/slot-$slot_index"
    local lock_dir="$slot_path/.slot-lock.d"

    if [ -d "$lock_dir" ]; then
      local pid
      pid="$(cat "$lock_dir/pid" 2>/dev/null || echo "")"

      if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        _log WARN "Recovering slot-$slot_index (PID $pid dead)"
        pool_release "$slot_path"
        recovered=$((recovered + 1))
      fi
    fi

    slot_index=$((slot_index + 1))
  done

  _log INFO "Recovered $recovered slot(s)"
  echo "$recovered"
}

# ---------------------------------------------------------------------------
# pool_nuke_slot -- Destroy and recreate a slot worktree
# Args: slot_path
# ---------------------------------------------------------------------------
pool_nuke_slot() {
  local slot_path="$1"

  _log WARN "Nuking slot at $slot_path"

  git -C "$REPO_PATH" worktree remove --force "$slot_path" 2>/dev/null || true
  git -C "$REPO_PATH" worktree prune

  if ! git -C "$REPO_PATH" worktree add "$slot_path" --detach; then
    _log ERROR "Failed to recreate worktree at $slot_path"
    return 1
  fi

  _log INFO "Recreated worktree at $slot_path"
  return 0
}
