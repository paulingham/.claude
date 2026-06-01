#!/usr/bin/env bash
# Config Protection — PreToolUse hook for Write and Edit
# Blocks modifications to linter/formatter config files.
# Prevents agents from weakening linting rules to pass checks.
# Hard block (exit 2).
#
# enforces: protocols/agent-protocol.md:Portable Config Dir
# protects: harness-config

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Subagent worktrees: linter/formatter configs in a worktree are scaffold/setup
# work or branch-scoped experiments that still face code review before merge.
# Block at the top-level project root only — that is the surface where "weaken
# the rules to pass" would actually escape into main. Matches the worktree-
# path allowance in orchestrator-discipline.sh.
if [[ "$FILE_PATH" =~ /\.claude/worktrees/ ]]; then
    exit 0
fi

BASENAME=$(basename "$FILE_PATH")

# Check against known linter/formatter config patterns
case "$BASENAME" in
    .eslintrc|.eslintrc.js|.eslintrc.json|.eslintrc.yml|.eslintrc.yaml|.eslintrc.cjs)
        ;;
    eslint.config.js|eslint.config.mjs|eslint.config.cjs|eslint.config.ts)
        ;;
    .prettierrc|.prettierrc.js|.prettierrc.json|.prettierrc.yml|.prettierrc.yaml|.prettierrc.cjs|.prettierrc.mjs|.prettierrc.toml)
        ;;
    prettier.config.js|prettier.config.mjs|prettier.config.cjs|prettier.config.ts)
        ;;
    biome.json|biome.jsonc)
        ;;
    .ruff.toml|ruff.toml)
        ;;
    .stylelintrc|.stylelintrc.json|.stylelintrc.yml|.stylelintrc.yaml|.stylelintrc.js|.stylelintrc.cjs)
        ;;
    .markdownlint.json|.markdownlint.yml|.markdownlint.yaml|.markdownlintrc)
        ;;
    *)
        exit 0
        ;;
esac

echo "BLOCKED: Agents must not modify linter/formatter configs ($BASENAME). Fix the code, not the rules." >&2
exit 2
