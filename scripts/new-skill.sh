#!/usr/bin/env bash
# new-skill.sh — scaffold a reference/clean-code skill under skills/<name>/.
# Usage: new-skill.sh [--dry-run] <skill-name>
# WHY: manually creating skills/*/SKILL.md without bumping README causes CI failure;
#      this script keeps the filesystem and README count in sync atomically.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${CLAUDE_ONRAMP_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
# shellcheck source=_lib/onramp-common.sh
source "$SCRIPT_DIR/_lib/onramp-common.sh"

TEMPLATE="$REPO_ROOT/templates/skill-reference/SKILL.md"
DRY_RUN=0
SKILL_NAME=""

_usage() {
  echo "Usage: $0 [--dry-run] <skill-name-kebab-case>" >&2
  echo "  --dry-run  print proposed changes without writing" >&2
  exit 1
}

_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --help|-h) _usage ;;
      -*) echo "unknown option: $1" >&2; _usage ;;
      *) SKILL_NAME="$1"; shift ;;
    esac
  done
  [[ -n "$SKILL_NAME" ]] || _usage
  _oc_validate_name "$SKILL_NAME"
}

_current_skill_count() {
  local all count
  all=$(find "$REPO_ROOT/skills" -maxdepth 2 -name "SKILL.md" 2>/dev/null)
  count=0
  while IFS= read -r f; do
    local dir; dir="$(dirname "$f")"
    [[ "$(basename "$dir")" != "_template" ]] && count=$((count+1))
  done <<< "$all"
  echo "$count"
}

_print_diff() {
  local dest="$1" cur="$2" new_count="$3"
  echo "=== Proposed changes ==="
  echo "  CREATE $dest"
  echo "  UPDATE README.md: ## Skills ($cur) -> ## Skills ($new_count)"
  echo "  UPDATE README.md: # $cur skills -> # $new_count skills (arch diagram)"
}

_create_skill() {
  local dest="$1" cur="$2" new_count="$3"
  mkdir -p "$(dirname "$dest")"
  sed "s/your-skill-name-kebab-case/$SKILL_NAME/" "$TEMPLATE" > "$dest"
  sed -i.bak \
    -e "s/## Skills ($cur)/## Skills ($new_count)/" \
    -e "s/# $cur skills/# $new_count skills/" \
    "$REPO_ROOT/README.md" && rm -f "$REPO_ROOT/README.md.bak"
  echo "  Created: $dest"
  echo "  Updated: README.md Skills count -> $new_count"
}

main() {
  _parse_args "$@"
  local dest="$REPO_ROOT/skills/$SKILL_NAME/SKILL.md"
  [[ -e "$dest" ]] && { echo "skill already exists: $dest" >&2; exit 1; }
  local cur; cur="$(_current_skill_count)"
  local new_count=$((cur+1))
  _print_diff "$dest" "$cur" "$new_count"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "(dry-run — nothing written)"
    exit 0
  fi
  if _oc_confirm; then
    _create_skill "$dest" "$cur" "$new_count"
  else
    echo "Aborted." >&2
    exit 1
  fi
}

main "$@"
