#!/usr/bin/env bash
# github.sh -- GitHub Issues backend using gh CLI
# Implements the backend_* contract (see backend.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

if ! declare -f _log >/dev/null 2>&1; then
  _log() { local level="$1"; shift; echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [$level] $*" >&2; }
fi

# --- Retry wrapper ----------------------------------------------------------

_gh_retry() {
  local max_attempts=3 attempt=1
  while [ "$attempt" -le "$max_attempts" ]; do
    if "$@" 2>/tmp/gh-stderr-$$; then
      rm -f /tmp/gh-stderr-$$
      return 0
    fi
    _log WARN "gh command failed (attempt $attempt/$max_attempts): $*"
    [ "$attempt" -lt "$max_attempts" ] && sleep $((attempt * 2))
    attempt=$((attempt + 1))
  done
  cat /tmp/gh-stderr-$$ >&2 2>/dev/null
  rm -f /tmp/gh-stderr-$$
  return 1
}

_gh_repo() { echo "$GH_OWNER/$GH_REPO"; }

_issue_number() { echo "${1#\#}"; }

_extract_acceptance_criteria() {
  local body="$1"
  local ac
  ac="$(echo "$body" | sed -n '/^## [Aa]cceptance [Cc]riteria/,/^## /{ /^## [Aa]cceptance/d; /^## /d; p; }')"
  [ -z "$ac" ] && ac="$(echo "$body" | sed -n '/^## AC$/,/^## /{ /^## AC$/d; /^## /d; p; }')"
  echo "${ac:-Not specified}"
}

_derive_issue_type() {
  local labels_json="$1"
  if echo "$labels_json" | jq -e '.[] | select(.name == "bug")' >/dev/null 2>&1; then
    echo "Bug"
  elif echo "$labels_json" | jq -e '.[] | select(.name == "feature")' >/dev/null 2>&1; then
    echo "Feature"
  else
    echo "Task"
  fi
}

_derive_priority() {
  local labels_json="$1"
  local pri
  pri="$(echo "$labels_json" | jq -r '[.[] | .name | select(startswith("priority:"))] | first // ""' 2>/dev/null)"
  case "$pri" in
    priority:high|priority:critical) echo "High" ;;
    priority:low) echo "Low" ;;
    *) echo "Medium" ;;
  esac
}

# --- Backend contract -------------------------------------------------------

backend_health_check() {
  if ! _gh_retry gh auth status >/dev/null 2>&1; then
    _log ERROR "GitHub authentication failed"
    return 1
  fi
  if ! _gh_retry gh api "repos/$(_gh_repo)" >/dev/null 2>&1; then
    _log ERROR "Cannot access repo $(_gh_repo)"
    return 2
  fi
  _log INFO "GitHub authenticated, repo $(_gh_repo) accessible"
  return 0
}

backend_poll_ready_tickets() {
  local limit="${1:-$POOL_SIZE}"
  local response
  response="$(_gh_retry gh issue list \
    --repo "$(_gh_repo)" \
    --label "$GH_READY_LABEL" \
    --state open \
    --limit "$limit" \
    --json number,title,labels)" || {
    _log ERROR "Failed to poll GitHub issues"
    return 1
  }
  echo "$response" | jq '{tickets: [.[] | {key: ("#" + (.number | tostring)), summary: .title}]}'
}

backend_get_ticket() {
  local key="$1"
  local number; number="$(_issue_number "$key")"
  local response
  response="$(_gh_retry gh issue view "$number" \
    --repo "$(_gh_repo)" \
    --json number,title,body,labels,assignees,milestone)" || {
    _log ERROR "Failed to fetch issue $key"
    return 1
  }

  local title body labels_json label_names
  title="$(echo "$response" | jq -r '.title // ""')"
  body="$(echo "$response" | jq -r '.body // ""')"
  labels_json="$(echo "$response" | jq '.labels // []')"
  label_names="$(echo "$labels_json" | jq -r '[.[].name] | join(", ")')"

  local issue_type priority ac url
  issue_type="$(_derive_issue_type "$labels_json")"
  priority="$(_derive_priority "$labels_json")"
  ac="$(_extract_acceptance_criteria "$body")"
  url="https://github.com/$(_gh_repo)/issues/$number"

  jq -n \
    --arg key "$key" \
    --arg summary "$title" \
    --arg description "$body" \
    --arg issue_type "$issue_type" \
    --arg priority "$priority" \
    --arg components "" \
    --arg labels "$label_names" \
    --arg parent_key "" \
    --arg acceptance_criteria "$ac" \
    --arg url "$url" \
    --argjson raw "$response" \
    '{key:$key,summary:$summary,description:$description,
      issue_type:$issue_type,priority:$priority,components:$components,
      labels:$labels,parent_key:$parent_key,
      acceptance_criteria:$acceptance_criteria,url:$url,raw:$raw}'
}

backend_claim_ticket() {
  local key="$1"
  local number; number="$(_issue_number "$key")"
  _gh_retry gh issue edit "$number" \
    --repo "$(_gh_repo)" \
    --add-label "$GH_IN_PROGRESS_LABEL" \
    --remove-label "$GH_READY_LABEL" >/dev/null || {
    _log WARN "Could not update labels on $key"
  }
  if [ -n "${GH_BOT_ACCOUNT:-}" ]; then
    _gh_retry gh issue edit "$number" \
      --repo "$(_gh_repo)" \
      --add-assignee "$GH_BOT_ACCOUNT" >/dev/null 2>&1 || true
  fi
  _gh_retry gh issue comment "$number" \
    --repo "$(_gh_repo)" \
    --body "Claude automation started processing this issue." >/dev/null || {
    _log WARN "Could not post start comment on $key"
  }
  _log INFO "Claimed issue $key"
}

backend_post_comment() {
  local key="$1" text="$2"
  local number; number="$(_issue_number "$key")"
  _gh_retry gh issue comment "$number" \
    --repo "$(_gh_repo)" \
    --body "$text" >/dev/null || {
    _log ERROR "Failed to comment on $key"
    return 1
  }
  _log INFO "Added comment to $key"
}

backend_complete_ticket() {
  local key="$1" pr_url="$2" cost="$3" duration="$4"
  local number; number="$(_issue_number "$key")"
  local comment
  comment="$(printf 'Claude automation completed successfully.\n\nPR: %s\nCost: $%s\nDuration: %s seconds' "$pr_url" "$cost" "$duration")"
  _gh_retry gh issue comment "$number" \
    --repo "$(_gh_repo)" --body "$comment" >/dev/null 2>&1 || true
  _gh_retry gh issue edit "$number" \
    --repo "$(_gh_repo)" \
    --remove-label "$GH_IN_PROGRESS_LABEL" \
    --add-label "$GH_DONE_LABEL" >/dev/null 2>&1 || true
  _gh_retry gh issue close "$number" \
    --repo "$(_gh_repo)" --reason completed >/dev/null 2>&1 || true
  _log INFO "Completed issue $key"
}

backend_fail_ticket() {
  local key="$1" exit_code="$2" stderr_tail="$3" duration="$4"
  local number; number="$(_issue_number "$key")"
  local comment
  comment="$(printf 'Claude automation failed.\n\nExit code: %s\nDuration: %s seconds\n\nLast output:\n%s' "$exit_code" "$duration" "$stderr_tail")"
  _gh_retry gh issue comment "$number" \
    --repo "$(_gh_repo)" --body "$comment" >/dev/null 2>&1 || true
  _gh_retry gh issue edit "$number" \
    --repo "$(_gh_repo)" \
    --remove-label "$GH_IN_PROGRESS_LABEL" \
    --add-label "$GH_BLOCKED_LABEL" >/dev/null 2>&1 || true
  _log INFO "Failed issue $key"
}

backend_ticket_url() {
  local key="$1"
  local number; number="$(_issue_number "$key")"
  echo "https://github.com/$(_gh_repo)/issues/$number"
}
