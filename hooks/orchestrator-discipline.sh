#!/bin/bash
# Orchestrator Discipline Hook — PreToolUse hook for Write and Edit tools
#
# Blocks the orchestrator from writing source files directly.
# The orchestrator must delegate all file changes to agents via skills.
#
# ALLOW: .md files (config/documentation in any path)
# BLOCK: all other file types (.ts, .tsx, .js, .jsx, .sh, .json, .yaml, etc.)

# Hook profile (minimal — always runs as a blocking hook)
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0

FILE_PATH="${CLAUDE_FILE_PATH:-}"

# No file path — allow (tool may not target a file)
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Allow markdown files — these are config/documentation
if [[ "$FILE_PATH" =~ \.md$ ]]; then
    exit 0
fi

# Block all other file types
echo "BLOCKED: Orchestrator cannot write source files directly. Delegate to an agent via the appropriate skill." >&2
exit 2
