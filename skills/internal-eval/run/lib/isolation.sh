#!/usr/bin/env bash
# Isolation env-var contract for inner /pipeline runs spawned by run-case.sh.
# Canonical contract: skills/internal-eval/run/ISOLATION.md.

# export_isolation_env <run-id> <case-id> <shadow-home>
# Sets the 7 variables that keep inner pipelines from colliding with outer state.
export_isolation_env() {
  local run_id="$1"; local case_id="$2"; local shadow_home="$3"
  local task_id="eval-${run_id}-${case_id}"
  mkdir -p "$shadow_home"
  _export_pipeline_vars "$task_id"
  _export_eval_vars "$run_id" "$case_id" "$shadow_home"
}

_export_pipeline_vars() {
  export CLAUDE_PIPELINE_TASK_ID="$1"
  export CLAUDE_PIPELINE_BYPASS=1
  export CLAUDE_DISABLE_AUTO_LEARN=1
  export CLAUDE_PROJECT_HASH="$1"
}

_export_eval_vars() {
  export EVAL_RUN_ID="$1"
  export EVAL_CASE_ID="$2"
  export HOME="$3"
}

# shadow_home_path <run-dir> <case-id>   -- canonical shadow-root for inner HOME
shadow_home_path() { echo "$1/home/$2"; }

# inner_state_dir <run-dir> <case-id>    -- where inner pipeline-state/ lands
inner_state_dir()  { echo "$1/inner/$2"; }

# mount_harness_root <shadow-home> <harness-root>
# Symlinks $shadow_home/.claude → harness-root so inner skill resolution
# (which reads $HOME/.claude/...) finds the pinned worktree.
mount_harness_root() {
  mkdir -p "$1"
  ln -snf "$2" "$1/.claude"
}
