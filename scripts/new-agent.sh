#!/usr/bin/env bash
# new-agent.sh — scaffold a new agent definition under agents/<name>.md.
# Usage: new-agent.sh [--dry-run] <agent-name>
# WHY: agents/*.md is globbed by the agent-table test (test_claude_md_agent_table.py);
#      adding a file without updating CLAUDE.md + README count breaks CI.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_ONRAMP_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=_lib/onramp-common.sh
source "$SCRIPT_DIR/_lib/onramp-common.sh"

TEMPLATE="$REPO_ROOT/templates/agent-template.md"
DRY_RUN=0
AGENT_NAME=""

_usage() {
  echo "Usage: $0 [--dry-run] <agent-name-kebab-case>" >&2
  echo "  --dry-run  print proposed changes without writing" >&2
  exit 1
}

_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --help|-h) _usage ;;
      -*) echo "unknown option: $1" >&2; _usage ;;
      *) AGENT_NAME="$1"; shift ;;
    esac
  done
  [[ -n "$AGENT_NAME" ]] || _usage
  _oc_validate_name "$AGENT_NAME"
}

_current_agent_count() {
  find "$REPO_ROOT/agents" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' '
}

_print_diff() {
  local dest="$1" new_count="$2"
  echo "=== Proposed changes ==="
  echo "  CREATE $dest"
  echo "  UPDATE README.md: agent count -> $new_count"
  echo "  UPDATE CLAUDE.md: add row to ### Agent Team table (you must fill in Phase/Worktree/Tunable)"
}

_create_agent() {
  local dest="$1" new_count="$2"
  sed "s/your-agent-name/$AGENT_NAME/g" "$TEMPLATE" > "$dest"
  sed -i.bak \
    "s/# [0-9]* specialized agent/# $new_count specialized agent/" \
    "$REPO_ROOT/README.md" && rm -f "$REPO_ROOT/README.md.bak"
  echo "  Created: $dest"
  echo "  Updated: README.md agent count -> $new_count"
  echo ""
  echo "  NEXT: add a 5-column row to the ### Agent Team table in CLAUDE.md:"
  echo "  | $AGENT_NAME | <Phase> | <Yes/No> | <sonnet/opus> | <Yes/No> |"
}

main() {
  _parse_args "$@"
  local dest="$REPO_ROOT/agents/$AGENT_NAME.md"
  [[ -e "$dest" ]] && { echo "agent already exists: $dest" >&2; exit 1; }
  local cur; cur="$(_current_agent_count)"
  local new_count=$((cur+1))
  _print_diff "$dest" "$new_count"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "(dry-run — nothing written)"
    exit 0
  fi
  if _oc_confirm; then
    _create_agent "$dest" "$new_count"
  else
    echo "Aborted." >&2
    exit 1
  fi
}

main "$@"
