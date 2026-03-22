#!/bin/bash
# SubagentStop hook: log agent completion and remind about worktree validation
# Exit 0 = proceed, stdout added to Claude's context

# Hook profile
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // .agent_type // "unknown"' 2>/dev/null)

# Write-capable agents may have worktree changes to merge
case "$AGENT_TYPE" in
  software-engineer|frontend-engineer|qa-engineer|database-engineer|infrastructure-engineer)
    echo "Write-capable agent ($AGENT_TYPE) completed. Before merging worktree: 1) Run tests on the worktree changes, 2) Check for merge conflicts with main, 3) Update pipeline state in memory/ if applicable."
    ;;
  code-reviewer|security-engineer|product-reviewer|architect)
    # Read-only agents — no merge action needed
    ;;
  *)
    # Unknown agent type — log for visibility
    echo "Agent ($AGENT_TYPE) completed."
    ;;
esac

exit 0
