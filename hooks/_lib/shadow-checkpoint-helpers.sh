#!/usr/bin/env bash
# Helper module for hooks/shadow-git-checkpoint.sh.
#
# Extraction rationale (per F4 + F8 archaeology — "_lib/ split by responsibility,
# not LOC"): both hook-side AND skill-side cleanup need (a) worktree resolution
# and (b) task-id resolution. Identical key derivation is enforced via shared
# helpers, mirroring hooks/_lib/runtime-guard-key.sh. Absent extraction, hook +
# Reflect-cleanup snippets would drift on edge cases (hostile slugs, missing
# files, BSD realpath).
#
# Bash 3.2 / BSD-portable. No GNU-only awk capture-groups. No flock.
# Path-traversal validation on every external string used in a path or ref name
# (per F6 instinct — OWASP A01).
#
# Public API (`_sgc_` prefix):
#   _sgc_resolve_worktree FILE_PATH    → echoes WT abs path, exit 0; else exit 1
#   _sgc_resolve_task_id               → echoes task-id, exit 0; else exit 1
#   _sgc_validate_id ID                → exit 0 if ID matches ^[A-Za-z0-9_.-]+$
#   _sgc_increment_counter TASK_DIR SLUG → echoes 4-digit zero-padded N
#   _sgc_ref_name TASK SLUG STEP       → echoes refs/checkpoints/<task>/<slug>-<step>

# ---------------------------------------------------------------------------
# AC1.3 — _sgc_validate_id
# ---------------------------------------------------------------------------
_sgc_validate_id() {
  local id="${1:-}"
  [[ -z "$id" ]] && return 1
  [[ "$id" =~ ^[A-Za-z0-9_.-]+$ ]] || return 1
  # Reject literal `..` (path-traversal). The regex above blocks `/`, whitespace,
  # quotes, control chars; we only need to reject pure-dot tokens explicitly.
  [[ "$id" == ".." || "$id" == "." ]] && return 1
  return 0
}

# ---------------------------------------------------------------------------
# AC1.1 — _sgc_resolve_worktree
# ---------------------------------------------------------------------------
# Walk up from the realpath'd parent of FILE_PATH; echo the first ancestor whose
# basename matches `agent-*` AND whose grandparent is `.claude/worktrees`.
_sgc_resolve_worktree() {
  local file_path="${1:-}"
  [[ -z "$file_path" ]] && return 1

  # F8 — BSD realpath returns empty for non-existent paths. python3 os.path.realpath
  # tolerates missing tail components (resolves to the longest prefix that exists,
  # then appends the missing tail).
  local resolved
  resolved=$(python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$file_path" 2>/dev/null)
  [[ -z "$resolved" ]] && return 1

  # If the file path itself doesn't exist, walk up from its parent dir.
  local cursor="$resolved"
  if [[ ! -e "$cursor" ]]; then
    cursor=$(dirname "$cursor")
  fi
  # Walk up until we find <prefix>/.claude/worktrees/agent-<rest>
  while [[ "$cursor" != "/" && -n "$cursor" ]]; do
    local parent base grandparent
    parent=$(dirname "$cursor")
    base=$(basename "$cursor")
    grandparent=$(basename "$parent")
    if [[ "$base" == agent-* && "$grandparent" == "worktrees" ]]; then
      # Confirm parent's parent ends in `.claude` (avoid spurious `worktrees`).
      local greatgrand
      greatgrand=$(basename "$(dirname "$parent")")
      if [[ "$greatgrand" == ".claude" ]]; then
        printf '%s\n' "$cursor"
        return 0
      fi
    fi
    cursor="$parent"
  done
  return 1
}

# ---------------------------------------------------------------------------
# AC1.2 — _sgc_resolve_task_id
# ---------------------------------------------------------------------------
# Primary: CLAUDE_PIPELINE_TASK_ID env var. Fallback: parse first active pipeline
# state file. Caches the result in TMPDIR keyed by session-id (R4 mitigation).
_sgc_resolve_task_id() {
  if [[ -n "${CLAUDE_PIPELINE_TASK_ID:-}" ]]; then
    printf '%s\n' "$CLAUDE_PIPELINE_TASK_ID"
    return 0
  fi

  local sid="${CLAUDE_SESSION_ID:-local-$$}"
  sid="${sid//[^A-Za-z0-9_-]/}"
  [[ -z "$sid" ]] && sid="local-$$"
  local cache="${TMPDIR:-/tmp}/claude-checkpoint-task-${sid}"
  if [[ -f "$cache" ]]; then
    local cached
    cached=$(cat "$cache" 2>/dev/null)
    if [[ -n "$cached" ]]; then
      printf '%s\n' "$cached"
      return 0
    fi
  fi

  local state_dir="${CLAUDE_PIPELINE_STATE_DIR:-$HOME/.claude/pipeline-state}"
  [[ ! -d "$state_dir" ]] && return 1

  # Discover an active in-progress pipeline state file. Use the canonical
  # _psp_find_active_pipelines helper when sourceable; otherwise fall back to a
  # shallow find. NB: this path is only hit when CLAUDE_PIPELINE_TASK_ID is unset.
  local helpers="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/pipeline-state-paths.sh"
  local active=""
  if [[ -f "$helpers" ]]; then
    # shellcheck source=/dev/null
    source "$helpers"
    active=$(_psp_find_active_pipelines "$state_dir" 2>/dev/null \
      | xargs grep -l "verdict: in_progress" 2>/dev/null | head -1)
  fi
  if [[ -z "$active" ]]; then
    active=$(find "$state_dir" -maxdepth 3 -name "pipeline.md" -type f 2>/dev/null \
      | xargs grep -l "verdict: in_progress" 2>/dev/null | head -1)
  fi
  [[ -z "$active" ]] && return 1

  local task
  task=$(grep -E '^task_id:' "$active" 2>/dev/null | head -1 | sed -E 's/^task_id:[[:space:]]*//' | tr -d ' ')
  [[ -z "$task" ]] && return 1
  _sgc_validate_id "$task" || return 1

  printf '%s\n' "$task" > "$cache" 2>/dev/null || true
  printf '%s\n' "$task"
  return 0
}

# ---------------------------------------------------------------------------
# AC1.4 — _sgc_increment_counter (mkdir-as-mutex; bash 3.2 / BSD safe)
# ---------------------------------------------------------------------------
# Atomic increment of pipeline-state/{task}/checkpoint-counter-{slug}.txt.
# 50ms backoff × 20 retries (1s budget). Mutex released via per-call EXIT trap
# (subshell-scoped) — never leaks across helper invocations because each call
# runs in the caller's process; we use trap-on-RETURN-equivalent via explicit
# rmdir at the end. The function chooses an EXIT-trap-equivalent: explicit
# release on success path, plus a guarded release on the error/return paths.
_sgc_increment_counter() {
  local task_dir="${1:-}" slug="${2:-}"
  [[ -z "$task_dir" || -z "$slug" ]] && return 1
  _sgc_validate_id "$slug" || return 1
  mkdir -p "$task_dir" 2>/dev/null || return 1

  local counter="$task_dir/checkpoint-counter-${slug}.txt"
  local lock="${counter}.lock"
  local i=0 max=20
  while ! mkdir "$lock" 2>/dev/null; do
    i=$((i + 1))
    if [[ $i -ge $max ]]; then
      return 1
    fi
    sleep 0.05
  done

  local current=0 next padded
  if [[ -f "$counter" ]]; then
    current=$(cat "$counter" 2>/dev/null | tr -d ' \t\n')
    [[ -z "$current" || ! "$current" =~ ^[0-9]+$ ]] && current=0
  fi
  next=$((10#$current + 1))
  printf '%d\n' "$next" > "$counter" 2>/dev/null
  rmdir "$lock" 2>/dev/null || true

  printf '%04d\n' "$next"
  return 0
}

# ---------------------------------------------------------------------------
# AC1.5 — _sgc_ref_name (validates BOTH task and slug before constructing ref)
# ---------------------------------------------------------------------------
_sgc_ref_name() {
  local task="${1:-}" slug="${2:-}" step="${3:-}"
  _sgc_validate_id "$task" || return 1
  _sgc_validate_id "$slug" || return 1
  [[ -z "$step" ]] && return 1
  [[ "$step" =~ ^[A-Za-z0-9_.-]+$ ]] || return 1
  printf 'refs/checkpoints/%s/%s-%s\n' "$task" "$slug" "$step"
  return 0
}
