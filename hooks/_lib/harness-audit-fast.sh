#!/usr/bin/env bash
# Fast harness audit checks for harness-audit-advisory.sh (≤2s budget)
# Subset of full /harness-audit. File existence + JSON validity + frontmatter presence.
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"

_haf_check_settings_json() {
  local f="$HARNESS_ROOT/settings.json"
  [[ -f "$f" ]] || { echo "CRITICAL: settings.json missing"; return 1; }
  jq -e . "$f" >/dev/null 2>&1 || { echo "CRITICAL: settings.json invalid JSON"; return 1; }
  return 0
}

_haf_count_orphan_hooks() {
  local hooks_dir="$HARNESS_ROOT/hooks" count=0
  while IFS= read -r f; do
    grep -qF "$(basename "$f")" "$HARNESS_ROOT/settings.json" 2>/dev/null || count=$((count+1))
  done < <(find "$hooks_dir" -maxdepth 1 -name "*.sh" 2>/dev/null)
  echo "$count"
}

_haf_check_agents_frontmatter() {
  local agents_dir="$HARNESS_ROOT/agents" count=0
  while IFS= read -r f; do
    grep -q "^name:" "$f" 2>/dev/null && grep -q "^tools:" "$f" 2>/dev/null || count=$((count+1))
  done < <(find "$agents_dir" -maxdepth 1 -name "*.md" 2>/dev/null)
  echo "$count"
}

_haf_run_all() {
  local criticals=0 warnings=0 o a
  _haf_check_settings_json || criticals=$((criticals+1))
  o=$(_haf_count_orphan_hooks); warnings=$((warnings+o))
  a=$(_haf_check_agents_frontmatter); warnings=$((warnings+a))
  echo "criticals=$criticals warnings=$warnings"
}
