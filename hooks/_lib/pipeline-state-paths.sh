#!/usr/bin/env bash
# Slice A — DUAL_PATH pipeline-state path helpers (bash 3.2 portable).
# New: `pipeline-state/{task}/{phase}.md`; Legacy: `pipeline-state/{task}-{phase}.md`.
# Workstream beats root on collision; fresher mtime wins within layout-class.

_psp_phase_list() {
  printf '%s\n' pipeline intake plan build review verify test accept ship debug \
    discussion best-of-n plan-validation product-brief tech-stack ui-architecture \
    design-brief greenfield boundary-analysis forensics
}

_psp_task_state_path() {
  local task="$1" phase="$2" ws="${3:-}"
  [[ -n "$ws" ]] && { printf 'pipeline-state/workstreams/%s/%s/%s.md\n' "$ws" "$task" "$phase"; return; }
  printf 'pipeline-state/%s/%s.md\n' "$task" "$phase"
}

_psp_legacy_state_path() {
  local task="$1" phase="$2" ws="${3:-}"
  [[ -n "$ws" ]] && { printf 'pipeline-state/workstreams/%s/%s-%s.md\n' "$ws" "$task" "$phase"; return; }
  printf 'pipeline-state/%s-%s.md\n' "$task" "$phase"
}

_psp_verification_evidence_path() {
  local task="$1" ws="${2:-}"
  [[ -n "$ws" ]] && { printf 'pipeline-state/workstreams/%s/%s/verification-evidence.json\n' "$ws" "$task"; return; }
  printf 'pipeline-state/%s/verification-evidence.json\n' "$task"
}

_psp_find_active_pipelines() {
  local dir="${1:-${HOME}/.claude/pipeline-state}"
  PSP_DIR="$dir" python3 "$(dirname "${BASH_SOURCE[0]}")/pipeline_state_paths_cli.py" find
}

_psp_discover_state_path() {
  local task="$1" phase="$2" ws="${3:-}"
  PSP_DIR="${HOME}/.claude/pipeline-state" python3 \
    "$(dirname "${BASH_SOURCE[0]}")/pipeline_state_paths_cli.py" discover "$task" "$phase" "$ws"
}

_psp_pipeline_active() {
  local task="$1"
  _psp_find_active_pipelines | xargs -I {} grep -l "task_id: $task" {} 2>/dev/null \
    | xargs grep -l "verdict: in_progress" 2>/dev/null | grep -q .
}
