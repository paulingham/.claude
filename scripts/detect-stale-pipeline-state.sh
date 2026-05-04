#!/usr/bin/env bash
# detect-stale-pipeline-state.sh — flag pipeline-state dirs whose `designated_branch`
# is already merged into origin/main but Reflect step 6d never cleaned up (typical
# cause: session crashed before Reflect). Reads <repo>/pipeline-state/*/pipeline.md
# (canonical) + legacy *-pipeline.md. Skipped fixtures: health-reports/, README.md,
# wave3-structural-cleanup/ (intentional fixture), workstreams/ (handled separately).
# Flags: --prune (print rm commands; does NOT run them), --json (JSONL output).
# Exit 0 if clean, 1 if any stale (so harness-audit can wire as a WARNING gate).
# NOTE: squash-merged branches that retained the original ref (e.g. reused across
# pipelines) are NOT flagged — `merge-base --is-ancestor` cannot detect those.
# Use the `pr` frontmatter field + `gh pr view` to cover that case when present.

set -uo pipefail

PRUNE=0; JSON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prune) PRUNE=1; shift ;;
    --json)  JSON=1;  shift ;;
    -h|--help) echo "Usage: $0 [--prune] [--json]"; exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[[ -z "$REPO_ROOT" ]] && { echo "Not in a git repo" >&2; exit 2; }
STATE_DIR="$REPO_ROOT/pipeline-state"
[[ -d "$STATE_DIR" ]] || { [[ "$JSON" -eq 0 ]] && echo "No pipeline-state/ directory at $STATE_DIR"; exit 0; }
mapfile -t FILES < <(find "$STATE_DIR" -maxdepth 2 -type f \
  \( -path "*/pipeline.md" -o -name "*-pipeline.md" \) \
  -not -path "*/health-reports/*" \
  -not -path "*/wave3-structural-cleanup/*" \
  -not -path "*/workstreams/*/*" 2>/dev/null | sort)

extract_field() {  # $1=path, $2=key
  awk -v key="$2" '
    /^---[[:space:]]*$/ { fm = !fm; next }
    fm && $0 ~ "^"key":" { sub("^"key":[[:space:]]*", ""); gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print; exit }
  ' "$1"
}

is_branch_in_main() {  # $1=branch name (e.g. claude/foo). returns 0 if merged.
  local sha
  sha=$(git -C "$REPO_ROOT" rev-parse "origin/$1" 2>/dev/null) || return 2
  git -C "$REPO_ROOT" merge-base --is-ancestor "$sha" origin/main 2>/dev/null
}

check_pr_state() {  # $1=pr number. echoes state or "" if gh unavailable.
  command -v gh >/dev/null 2>&1 || { echo ""; return; }
  gh pr view "$1" --json state -q .state 2>/dev/null || echo ""
}

stale_count=0
print_header() { printf '| %-44s | %-10s | %-50s | %-8s | %-8s |\n%s\n' "task_id (path)" "phase" "designated_branch" "merged?" "pr_state" "|---|---|---|---|---|"; }
[[ "$JSON" -eq 0 ]] && print_header

for f in "${FILES[@]}"; do
  task_id=$(extract_field "$f" task_id)
  phase=$(extract_field "$f" phase)
  branch=$(extract_field "$f" designated_branch)
  pr=$(extract_field "$f" pr)
  rel="${f#$REPO_ROOT/}"

  reason=""; pr_state=""
  if [[ -n "$branch" ]]; then
    if is_branch_in_main "$branch"; then reason="branch-merged"
    elif [[ $? -eq 2 ]]; then reason="branch-deleted"; fi
  fi
  [[ -n "$pr" ]] && pr_state=$(check_pr_state "$pr")
  [[ "$pr_state" == "MERGED" || "$pr_state" == "CLOSED" ]] && reason="${reason:-pr-$pr_state}"

  [[ -z "$reason" ]] && continue
  stale_count=$((stale_count + 1))

  if [[ "$JSON" -eq 1 ]]; then
    jq -nc --arg task "$task_id" --arg phase "$phase" --arg branch "$branch" \
           --arg pr "$pr" --arg pr_state "$pr_state" --arg reason "$reason" \
           --arg path "$rel" \
      '{task_id:$task,phase:$phase,designated_branch:$branch,pr:$pr,pr_state:$pr_state,reason:$reason,path:$path}'
  else
    printf '| %-44s | %-10s | %-50s | %-8s | %-8s |\n' \
      "$task_id ($rel)" "$phase" "${branch:-—}" "$reason" "${pr_state:-—}"
  fi
done

if [[ "$PRUNE" -eq 1 && "$stale_count" -gt 0 ]]; then
  echo; echo "# Suggested cleanup commands (review before running):"
  for f in "${FILES[@]}"; do
    branch=$(extract_field "$f" designated_branch)
    [[ -z "$branch" ]] && continue
    is_branch_in_main "$branch"; rc=$?
    [[ "$rc" -eq 0 || "$rc" -eq 2 ]] || continue   # 0=merged, 2=deleted (both stale)
    dir="$(dirname "$f")"
    [[ "$dir" == "$STATE_DIR" ]] && echo "rm $f" || echo "rm -rf $dir"
  done
fi

[[ "$stale_count" -gt 0 ]] && exit 1 || exit 0
