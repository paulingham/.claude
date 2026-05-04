#!/usr/bin/env bash
# Prompt Tracing Hook — PreToolUse on Agent|Skill.
#
# When CLAUDE_ENABLE_TRACE=1, captures the rendered prompt the orchestrator
# composed for the spawn (skill references + instincts + session memory +
# scratchpad + agent memory are already baked into tool_input.prompt or
# tool_input.args by the orchestrator — this hook writes that verbatim).
#
# Default off = zero overhead. Trace files land under
# ~/.claude/metrics/{session-id}/trace/{role}-{task-id}-{ts}.txt and are
# pruned (>7d) by trace-cleanup.sh on SessionStart.
#
# Never blocks the tool call — exits 0 on every failure path.
#
# enforces: rules/_detail/autonomous-intelligence.md:Prompt Tracing
# protects: debug-trace

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
trap 'log_hook_event $?' EXIT

set -uo pipefail

[[ "${CLAUDE_ENABLE_TRACE:-0}" == "1" ]] || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL_NAME" in
    Agent|Skill) ;;
    *) exit 0 ;;
esac

extract() {
    echo "$INPUT" | jq -r "$1 // empty" 2>/dev/null
}

if [[ "$TOOL_NAME" == "Agent" ]]; then
    role_raw=$(extract '.tool_input.subagent_type')
    model=$(extract '.tool_input.model')
    isolation=$(extract '.tool_input.isolation')
    team_name=$(extract '.tool_input.team_name')
    body=$(extract '.tool_input.prompt')
    agent_role="${role_raw:-unknown}"
else
    skill_name=$(extract '.tool_input.skill')
    body=$(extract '.tool_input.args')
    agent_role="skill:${skill_name:-unknown}"
    model=""
    isolation=""
    team_name=""
fi

session_id="${CLAUDE_SESSION_ID:-local-$$}"

# Resolve task_id + phase from the first pipeline-state file (best-effort, DUAL_PATH).
task_id="unknown"
phase="unknown"
pipeline_glob="${HOME}/.claude/pipeline-state"
shopt -s nullglob
pipeline_files=("$pipeline_glob"/*-pipeline.md "$pipeline_glob"/*/pipeline.md)
shopt -u nullglob
if (( ${#pipeline_files[@]} > 0 )); then
    first_pipeline="${pipeline_files[0]}"
    base=$(basename "$first_pipeline")
    if [[ "$base" == "pipeline.md" ]]; then
        task_id=$(basename "$(dirname "$first_pipeline")")
    else
        task_id="${base%-pipeline.md}"
    fi
    parsed_phase=$(grep -m1 '^phase:' "$first_pipeline" 2>/dev/null | awk '{print $2}')
    phase="${parsed_phase:-unknown}"
fi

dispatch="subagent"
[[ -n "$team_name" ]] && dispatch="team"
worktree="no"
[[ "$isolation" == "worktree" ]] && worktree="yes"

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
role_sanitized="${agent_role//:/-}"
role_sanitized="${role_sanitized//\//-}"

trace_dir="${HOME}/.claude/metrics/${session_id}/trace"
mkdir -p "$trace_dir" 2>/dev/null || { echo "trace-prompt: mkdir failed: $trace_dir" >&2; exit 0; }

trace_file="${trace_dir}/${role_sanitized}-${task_id}-${timestamp}.txt"

{
    printf '== SPAWN METADATA ==\n'
    printf 'timestamp: %s\n' "$timestamp"
    printf 'session_id: %s\n' "$session_id"
    printf 'task_id: %s\n' "$task_id"
    printf 'agent_role: %s\n' "$agent_role"
    printf 'model: %s\n' "${model:-default}"
    printf 'phase: %s\n' "$phase"
    printf 'dispatch: %s\n' "$dispatch"
    printf 'worktree: %s\n' "$worktree"
    printf '== RENDERED PROMPT ==\n'
    printf '%s\n' "$body"
    printf '== END ==\n'
} > "$trace_file" 2>/dev/null || echo "trace-prompt: write failed: $trace_file" >&2

exit 0
