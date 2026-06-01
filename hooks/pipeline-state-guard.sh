#!/usr/bin/env bash
# Pipeline State Guard — PreToolUse hook for Agent tool
#
# HARD BLOCK (exit 2): Write-capable agents cannot be spawned without
# an active pipeline state file in pipeline-state/. This ensures the
# orchestrator creates pipeline infrastructure (state, scratchpad,
# session memory) before any implementation work begins.
#
# Exceptions:
# - architect agents (read-only planning)
# - code-reviewer, security-engineer, product-reviewer (read-only review)
# - agents spawned with CLAUDE_PIPELINE_BYPASS=1 env var
#
# enforces: protocols/pipeline-protocol.md:Structured Pipeline State
# protects: pipeline

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Only check Agent tool
if [[ "$TOOL_NAME" != "Agent" ]]; then
    exit 0
fi

TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')

AGENT_TYPE=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    data = {}
print(data.get('subagent_type', '') or '')
" "$TOOL_INPUT" 2>/dev/null)

# Skip for read-only agent types
READ_ONLY_TYPES="architect code-reviewer security-engineer product-reviewer"
for ro_type in $READ_ONLY_TYPES; do
    if [[ "$AGENT_TYPE" == "$ro_type" ]]; then
        exit 0
    fi
done

# Skip for non-write-capable types
WRITE_CAPABLE_TYPES="software-engineer frontend-engineer qa-engineer database-engineer infrastructure-engineer"
IS_WRITE_CAPABLE=false
for wc_type in $WRITE_CAPABLE_TYPES; do
    if [[ "$AGENT_TYPE" == "$wc_type" ]]; then
        IS_WRITE_CAPABLE=true
        break
    fi
done

if [[ "$IS_WRITE_CAPABLE" != true ]]; then
    exit 0
fi

# Check for bypass env var (nested-pipeline isolation — see skills/internal-eval/run/ISOLATION.md)
if [[ "${CLAUDE_PIPELINE_BYPASS:-}" == "1" ]]; then
    echo "[guard] bypass: EVAL_RUN_ID=${EVAL_RUN_ID:-?} EVAL_CASE_ID=${EVAL_CASE_ID:-?}" >&2
    exit 0
fi

# Check for active pipeline state file — project-local first, then global fallback.
# DUAL_PATH: helper covers both legacy *-pipeline.md AND new {task-id}/pipeline.md
# AND excludes reserved root dirs (workstreams/, health-reports/) per
# pipeline_state_paths_helpers.EXCLUDED_ROOT_DIRS.
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/pipeline-state-paths.sh"
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
for PIPELINE_DIR in "$GIT_ROOT/pipeline-state" "$HOME/.claude/pipeline-state"; do
    if [[ -d "$PIPELINE_DIR" ]]; then
        ACTIVE_FILES=$(_psp_find_active_pipelines "$PIPELINE_DIR" 2>/dev/null | head -1)
        if [[ -n "$ACTIVE_FILES" ]]; then
            exit 0
        fi
    fi
done

echo "BLOCKED: No active pipeline state file found in pipeline-state/. Before spawning write-capable agents:" >&2
echo "  1. Create a pipeline state file: pipeline-state/{task-id}-pipeline.md" >&2
echo "  2. Or invoke /pipeline or /intake to set up the pipeline infrastructure" >&2
echo "  3. Or set CLAUDE_PIPELINE_BYPASS=1 in settings.json env for ad-hoc work" >&2
exit 2
