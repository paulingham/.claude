#!/usr/bin/env bash
# Intake Reminder — UserPromptSubmit hook
#
# Two modes:
#   1. HARD BLOCK (exit 2): Batch/wave keywords WITHOUT an active pipeline state.
#   2. ADVISORY (exit 0): Single-task implementation keywords.

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "UserPromptSubmit"
trap 'log_hook_event $?' EXIT

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)

PROMPT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    data = {}
prompt = data.get('prompt', '') or data.get('content', '') or data.get('message', '') or ''
print(prompt)
" "$INPUT" 2>/dev/null)

if [[ ${#PROMPT} -lt 10 ]]; then
    exit 0
fi

if [[ "$PROMPT" == /* ]]; then
    exit 0
fi

PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

if echo "$PROMPT_LOWER" | grep -qi '/intake\|/pipeline\|/bug-fix\|/refactor\|/build'; then
    exit 0
fi

# Check for batch/wave keywords — these REQUIRE pipeline infrastructure
HAS_BATCH_KEYWORD=false
for keyword in "start wave" "wave 2" "wave 3" "wave 4" "wave 5" "wave 6" "batch" "all prs" "parallel prs" "run all"; do
    if echo "$PROMPT_LOWER" | grep -qi "$keyword"; then
        HAS_BATCH_KEYWORD=true
        break
    fi
done

if [[ "$HAS_BATCH_KEYWORD" == true ]]; then
    # DUAL_PATH: matches both legacy *-pipeline.md AND new {task-id}/pipeline.md.
    PIPELINE_DIR="$HOME/.claude/pipeline-state"
    ACTIVE_FILES=""
    if [[ -d "$PIPELINE_DIR" ]]; then
        ACTIVE_FILES=$(find "$PIPELINE_DIR" \( -name "*-pipeline.md" -o -name "pipeline.md" \) -type f 2>/dev/null | head -1)
    fi

    if [[ -z "$ACTIVE_FILES" ]]; then
        echo "BLOCKED: Batch/wave work detected but no pipeline state exists. Invoke /intake or /pipeline first to set up pipeline infrastructure (state files, scratchpad, session memory, observation tracking)." >&2
        exit 2
    fi
fi

# Check for single-task implementation keywords (advisory only)
HAS_KEYWORD=false
for keyword in "implement" "build" "fix" "refactor" "add feature" "create feature" "add endpoint" "new feature"; do
    if echo "$PROMPT_LOWER" | grep -qi "$keyword"; then
        HAS_KEYWORD=true
        break
    fi
done

if [[ "$HAS_KEYWORD" == true ]]; then
    echo '{"systemMessage": "INTAKE REMINDER: This looks like implementation work. Invoke /intake first to classify and route through the pipeline."}'
fi

exit 0
