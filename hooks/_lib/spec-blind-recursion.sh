#!/usr/bin/env bash
# Recursion-detection helper for the spec-blind validator.
#
# Detects when the project repo IS the harness itself, in which case V1 emits
# SPEC_BLIND_INSUFFICIENT_SURFACE with reason `harness-internal-recursion`
# rather than attempting to author spec-blind tests against the harness's own
# .md / .sh files. (V2 augments the allowlist for harness-internal pipelines —
# see pipeline-state/spec-blind-validator-harness-aware-soak-end/pipeline.md.)
#
# Detection requires BOTH (per plan AC14, R1 strengthening — Eng #9):
#   1. ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/rules/core.md exists, AND
#   2. realpath($(git -C <cwd> rev-parse --show-toplevel)) ==
#      realpath(${CLAUDE_CONFIG_DIR:-$HOME/.claude})
#
# The `git remote` heuristic was considered and dropped — fragile across forks,
# mirrors, and stale remotes.
#
# Public function:
#   is_harness_internal_cwd <cwd>  — exit 0 (harness-internal) / 1 (not harness)

# Resolve a path to its realpath without depending on the GNU `realpath` binary
# (macOS BSD lacks the GNU flag set).
_spec_blind_realpath() {
  python3 -c 'import os.path,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null
}

is_harness_internal_cwd() {
  local cwd="$1"
  [[ -z "$cwd" ]] && return 1
  local config_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  # Condition 1: rules/core.md MUST exist under the config dir.
  [[ -f "$config_dir/rules/core.md" ]] || return 1
  # Condition 2: the cwd's repo top-level MUST resolve to the same realpath as
  # the config dir.
  local repo_top
  repo_top="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)"
  [[ -z "$repo_top" ]] && return 1
  local repo_real config_real
  repo_real="$(_spec_blind_realpath "$repo_top")"
  config_real="$(_spec_blind_realpath "$config_dir")"
  [[ -z "$repo_real" || -z "$config_real" ]] && return 1
  [[ "$repo_real" == "$config_real" ]] || return 1
  return 0
}
