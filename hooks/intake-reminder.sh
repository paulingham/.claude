#!/bin/bash
# Intake Reminder — UserPromptSubmit hook
#
# Advisory hook that reminds the orchestrator to invoke /intake before
# starting implementation work. Reads the user prompt from stdin JSON,
# checks for implementation keywords, and emits a systemMessage if the
# user hasn't already referenced a pipeline skill.
#
# Always exits 0 (advisory only, never blocking).

# Read JSON from stdin
INPUT=$(cat)

# Extract prompt text using python3
PROMPT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    data = {}
# Try common field names
prompt = data.get('prompt', '') or data.get('content', '') or data.get('message', '') or ''
print(prompt)
" "$INPUT" 2>/dev/null)

# Skip if prompt is very short
if [[ ${#PROMPT} -lt 10 ]]; then
    exit 0
fi

# Skip if prompt starts with / (already a skill invocation)
if [[ "$PROMPT" == /* ]]; then
    exit 0
fi

PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Check if prompt already mentions pipeline skills
if echo "$PROMPT_LOWER" | grep -qi '/intake\|/pipeline\|/bug-fix\|/refactor\|/build'; then
    exit 0
fi

# Check for implementation keywords
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
