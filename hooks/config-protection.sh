#!/bin/bash
# Config Protection — PreToolUse hook for Write and Edit
# Blocks modifications to linter/formatter config files.
# Prevents agents from weakening linting rules to pass checks.
# Hard block (exit 2).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

FILE_PATH="${CLAUDE_FILE_PATH:-}"

if [[ -z "$FILE_PATH" ]]; then
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
