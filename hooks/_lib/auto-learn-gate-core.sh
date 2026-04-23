#!/usr/bin/env bash
# Core gate evaluation for auto-learn-gate. Shape: <=5 lines/func.

_alg_hours_since() {
  local ts="$1"
  [[ -z "$ts" || "$ts" == "null" ]] && { echo 999; return; }
  local then_s now_s
  then_s=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts" +%s 2>/dev/null || date -u -d "$ts" +%s 2>/dev/null || echo 0)
  now_s=$(date -u +%s); echo $(( (now_s - then_s) / 3600 ))
}

_alg_current_pipeline_id() {
  local dir="$HOME/.claude/pipeline-state" f
  [[ -d "$dir" ]] || { echo ""; return; }
  f=$(grep -rl "in_progress" "$dir"/*-pipeline.md 2>/dev/null | head -1)
  [[ -n "$f" ]] && awk '/^task_id:/ {print $2; exit}' "$f" 2>/dev/null || echo ""
}

_alg_should_fire() {
  local obs="$1" pipes="$2" last_run="$3" cur_pid="$4" last_fired="$5" hrs
  [[ "$obs" -lt 3 ]] && return 1
  hrs=$(_alg_hours_since "$last_run")
  [[ "$pipes" -ge 3 || "$last_run" == "null" || "$last_run" == "" || "$hrs" -ge 24 ]] || return 1
  [[ -n "$cur_pid" && "$cur_pid" == "$last_fired" ]] && return 1
  return 0
}

_alg_print_trigger() {
  local obs="$1" pipes="$2"
  printf '%s\n' "═══════════════════════════════════════════════════════"
  printf '[auto-learn-gate] Triggered: %s observations, %s pipelines since last /learn\n' "$obs" "$pipes"
  printf 'Invoke /learn now to extract instincts before continuing.\n'
  printf '%s\n' "═══════════════════════════════════════════════════════"
}
