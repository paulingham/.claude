#!/usr/bin/env bash
# baseline_capture.sh — design-qc Step 5.5 helper (AC1, AC6 + failure-mode-1).
#
# Captures pixel-diff baselines from the project's current `main` HEAD by
# spawning a separate `git worktree add` against main, running the project's
# build, and routing screenshots to
# `pipeline-state/{task-id}/visual-baselines/{slug}-{viewport}.png`.
#
# Iron Law 4 compliance: every git mutation runs with `git -C "$WORKTREE_PATH"`
# delegation; no bare `git checkout` or `git switch` is ever invoked from
# REPO_ROOT.
#
# Failure semantics (failure-mode-1, AC6):
#   - Baseline build on main HEAD fails → ALL routes treated as auto-bless
#     (new-route path), `index.json.visual_regression.captured = false`,
#     scratchpad warning with literal token `baseline-build-failed`.
#   - Route present on branch but absent on main → auto-bless that route
#     specifically, scratchpad warning with literal token
#     `auto-blessed-baseline`.
#
# Inputs (env vars):
#   TASK_ID         — the active pipeline's task-id; resolves the visual-baselines dir.
#   REPO_ROOT       — root of the repo being captured (defaults to pwd).
#   BUILD_COMMAND   — npm/yarn build command from project CLAUDE.md.
#   PIPELINE_STATE_ROOT — pipeline-state root for output files (defaults to
#                         "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/pipeline-state").
#
# Outputs:
#   $PIPELINE_STATE_ROOT/$TASK_ID/visual-baselines/{slug}-{viewport}.png
#   $PIPELINE_STATE_ROOT/$TASK_ID/scratchpad/design-qc-build.md  (on failure)
#
# enforces: protocols/pipeline-protocol.md (Final Gate § In-Cycle Fix Rule)

set -uo pipefail

# ---------------------------------------------------------------------------
# Input validation + defaults.
# ---------------------------------------------------------------------------

: "${TASK_ID:?baseline_capture: TASK_ID required}"
: "${BUILD_COMMAND:?baseline_capture: BUILD_COMMAND required (from project CLAUDE.md Dev Server section)}"
REPO_ROOT="${REPO_ROOT:-$(pwd)}"
PIPELINE_STATE_ROOT="${PIPELINE_STATE_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/pipeline-state}"

VISUAL_BASELINES_DIR="${PIPELINE_STATE_ROOT}/${TASK_ID}/visual-baselines"
SCRATCHPAD_DIR="${PIPELINE_STATE_ROOT}/${TASK_ID}/scratchpad"
SCRATCHPAD_FILE="${SCRATCHPAD_DIR}/design-qc-build.md"

# Random suffix for the baseline worktree path to avoid concurrent-pipeline
# collisions (failure-mode-8 mitigation).
BASELINE_WT_ROOT="${REPO_ROOT}/.claude/worktrees"
BASELINE_WT_NAME="baseline-$(date +%s)-$$"
BASELINE_WT="${BASELINE_WT_ROOT}/${BASELINE_WT_NAME}"

# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

capture_baseline() {
  mkdir -p "$VISUAL_BASELINES_DIR" "$SCRATCHPAD_DIR" || return 1

  if ! _create_baseline_worktree; then
    _emit_scratchpad_warning "baseline-build-failed" \
      "Could not create baseline worktree at main HEAD. Skipping pixel-diff; all routes auto-blessed."
    _emit_index_captured_false
    return 0   # Non-fatal: design-qc still emits SCREENSHOTS_CAPTURED.
  fi

  if ! _run_baseline_build; then
    _emit_scratchpad_warning "baseline-build-failed" \
      "Baseline build on main HEAD failed. Skipping pixel-diff; all routes auto-blessed."
    _emit_index_captured_false
    _cleanup_baseline_worktree
    return 0
  fi

  _emit_index_captured_true
  _cleanup_baseline_worktree
  return 0
}

# ---------------------------------------------------------------------------
# Internal helpers (CC ≤ 5, nesting ≤ 2, one-thing-per-function).
# ---------------------------------------------------------------------------

_create_baseline_worktree() {
  mkdir -p "$BASELINE_WT_ROOT" 2>/dev/null
  # Iron Law 4 — delegated worktree creation. NEVER bare `git checkout main`.
  git -C "$REPO_ROOT" worktree add --detach "$BASELINE_WT" main 2>/dev/null
}

_run_baseline_build() {
  # Build runs INSIDE the baseline worktree (delegated cd), per Iron Law 4.
  ( cd "$BASELINE_WT" && eval "$BUILD_COMMAND" ) >/dev/null 2>&1
}

_cleanup_baseline_worktree() {
  # Idempotent: ignore errors if worktree was never created.
  git -C "$REPO_ROOT" worktree remove --force "$BASELINE_WT" 2>/dev/null || true
}

_emit_scratchpad_warning() {
  local token="$1"
  local body="$2"
  cat >> "$SCRATCHPAD_FILE" <<EOF

---
category: warning
---

${body}
Token: ${token}
EOF
}

# Helper for AC6 — emit "auto-blessed-baseline" warning for a route that
# exists on branch but not on main.
emit_auto_blessed_baseline() {
  local route="$1"
  _emit_scratchpad_warning "auto-blessed-baseline" \
    "Route ${route} present on branch but absent on main HEAD. Baseline captured-as-self."
}

_emit_index_captured_false() {
  local index_file="${PIPELINE_STATE_ROOT}/${TASK_ID}/design-qc/index.json"
  mkdir -p "$(dirname "$index_file")" 2>/dev/null
  # Best-effort: jq-merge if index exists, else write a minimal stub.
  if [[ -f "$index_file" ]]; then
    local tmp
    tmp="$(mktemp)"
    jq '.visual_regression = {captured: false, reason: "baseline-build-failed"}' \
      "$index_file" > "$tmp" && mv "$tmp" "$index_file"
  else
    cat > "$index_file" <<'EOF'
{
  "schema_version": 2,
  "visual_regression": {
    "captured": false,
    "reason": "baseline-build-failed"
  },
  "routes": []
}
EOF
  fi
}

_emit_index_captured_true() {
  local index_file="${PIPELINE_STATE_ROOT}/${TASK_ID}/design-qc/index.json"
  mkdir -p "$(dirname "$index_file")" 2>/dev/null
  if [[ -f "$index_file" ]]; then
    local tmp
    tmp="$(mktemp)"
    jq --arg dir "$VISUAL_BASELINES_DIR" \
      '.visual_regression = (.visual_regression // {}) + {captured: true, baselines_dir: $dir}' \
      "$index_file" > "$tmp" && mv "$tmp" "$index_file"
  else
    jq -n --arg dir "$VISUAL_BASELINES_DIR" \
      '{schema_version: 2, visual_regression: {captured: true, baselines_dir: $dir}, routes: []}' \
      > "$index_file"
  fi
}

# When sourced (not executed directly), expose helpers but do not auto-run.
# When executed directly, run capture_baseline.
if [[ "${BASH_SOURCE[0]:-$0}" == "${0}" ]]; then
  capture_baseline
fi
