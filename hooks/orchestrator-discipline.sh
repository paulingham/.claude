#!/bin/bash
# Orchestrator Discipline Hook — PreToolUse hook for Write and Edit tools
#
# Blocks the orchestrator from writing source files directly.
# The orchestrator must delegate all file changes to agents via skills.
#
# ALLOW: .md files (config/documentation in any path)
# ALLOW: .claude/automation/ (infrastructure scripts and config)
# ALLOW: .claude/hooks/ (hook scripts are infrastructure config)
# BLOCK: all other file types (.ts, .tsx, .js, .jsx, .json, .yaml, etc.)

# Hook profile (minimal — always runs as a blocking hook)
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# No file path — allow (tool may not target a file)
if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Allow markdown files — these are config/documentation
if [[ "$FILE_PATH" =~ \.md$ ]]; then
    exit 0
fi

# Allow automation infrastructure files — scripts, config, not app source
if [[ "$FILE_PATH" =~ \.claude/automation/ ]]; then
    exit 0
fi

# Allow hook files — infrastructure config, not app source
if [[ "$FILE_PATH" =~ \.claude/hooks/ ]]; then
    exit 0
fi

# Block all other file types
echo "BLOCKED: Orchestrator cannot write source files directly. Delegate to an agent via the appropriate skill." >&2
exit 2
