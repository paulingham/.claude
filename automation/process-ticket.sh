#!/usr/bin/env bash
# process-ticket.sh -- Per-ticket processing: claim slot, run Claude, update Jira
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/pool.sh"
source "$SCRIPT_DIR/backend.sh"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

slugify_summary() {
  local summary="$1"
  echo "$summary" \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]/-/g' \
    | sed 's/--*/-/g' \
    | sed 's/^-//;s/-$//' \
    | cut -c1-50
}

render_prompt() {
  local ticket_key="$1" ticket_json="$2" branch_name="$3"
  local template_path="$AUTOMATION_DIR/prompt-template.md"
  local tmp_prompt; tmp_prompt="$(mktemp)"

  local summary issue_type priority components labels epic_key
  summary="$(echo "$ticket_json" | jq -r '.summary // ""')"
  issue_type="$(echo "$ticket_json" | jq -r '.issue_type // ""')"
  priority="$(echo "$ticket_json" | jq -r '.priority // ""')"
  components="$(echo "$ticket_json" | jq -r '.components // ""')"
  labels="$(echo "$ticket_json" | jq -r '.labels // ""')"
  epic_key="$(echo "$ticket_json" | jq -r '.parent_key // ""')"

  local description acceptance_criteria
  description="$(echo "$ticket_json" | jq -r '.description // ""')"
  acceptance_criteria="$(echo "$ticket_json" | jq -r '.acceptance_criteria // "Not specified"')"

  # Write multiline fields to temp files for safe sed substitution
  local tmp_desc; tmp_desc="$(mktemp)"
  local tmp_ac; tmp_ac="$(mktemp)"
  printf '%s' "$description" > "$tmp_desc"
  printf '%s' "$acceptance_criteria" > "$tmp_ac"

  cp "$template_path" "$tmp_prompt"

  # Escape sed special characters in replacement values
  _sed_escape() { printf '%s' "$1" | sed 's/[&/\]/\\&/g'; }

  # Replace single-line placeholders
  sed -i '' "s/{{TICKET_KEY}}/$(_sed_escape "$ticket_key")/g" "$tmp_prompt"
  sed -i '' "s/{{SUMMARY}}/$(_sed_escape "$summary")/g" "$tmp_prompt"
  sed -i '' "s/{{ISSUE_TYPE}}/$(_sed_escape "$issue_type")/g" "$tmp_prompt"
  sed -i '' "s/{{PRIORITY}}/$(_sed_escape "$priority")/g" "$tmp_prompt"
  sed -i '' "s/{{COMPONENTS}}/$(_sed_escape "$components")/g" "$tmp_prompt"
  sed -i '' "s/{{LABELS}}/$(_sed_escape "$labels")/g" "$tmp_prompt"
  sed -i '' "s/{{EPIC_KEY}}/$(_sed_escape "$epic_key")/g" "$tmp_prompt"
  sed -i '' "s/{{BRANCH_NAME}}/$(_sed_escape "$branch_name")/g" "$tmp_prompt"

  # Replace multiline placeholders using sed with file-read approach
  # Use awk for multiline replacement to handle newlines safely
  _replace_multiline_placeholder "$tmp_prompt" "{{DESCRIPTION}}" "$tmp_desc"
  _replace_multiline_placeholder "$tmp_prompt" "{{ACCEPTANCE_CRITERIA}}" "$tmp_ac"

  rm -f "$tmp_desc" "$tmp_ac"
  cat "$tmp_prompt"
  rm -f "$tmp_prompt"
}

_replace_multiline_placeholder() {
  local file="$1" placeholder="$2" content_file="$3"
  local tmp_out; tmp_out="$(mktemp)"
  awk -v placeholder="$placeholder" -v content_file="$content_file" '
    {
      idx = index($0, placeholder)
      if (idx > 0) {
        prefix = substr($0, 1, idx - 1)
        suffix = substr($0, idx + length(placeholder))
        printf "%s", prefix
        while ((getline line < content_file) > 0) {
          print line
        }
        close(content_file)
        print suffix
      } else {
        print
      }
    }
  ' "$file" > "$tmp_out"
  mv "$tmp_out" "$file"
}

extract_pr_url() {
  local result_text="$1" branch_name="$2" slot_path="$3"

  local pr_url
  pr_url="$(echo "$result_text" | grep -oE 'https://github\.com/[^ ]*pull/[0-9]+' | head -1 || echo "")"

  if [ -z "$pr_url" ]; then
    pr_url="$(cd "$slot_path" && gh pr list --head "$branch_name" --json url -q '.[0].url' 2>/dev/null || echo "")"
  fi

  echo "$pr_url"
}

build_success_comment() {
  local pr_url="$1" cost="$2" duration="$3"
  printf 'Claude automation completed successfully.\n\nPR: %s\nCost: $%s\nDuration: %s seconds' \
    "$pr_url" "$cost" "$duration"
}

build_error_comment() {
  local exit_code="$1" stderr_tail="$2" duration="$3"
  printf 'Claude automation failed.\n\nExit code: %s\nDuration: %s seconds\n\nLast output:\n%s' \
    "$exit_code" "$duration" "$stderr_tail"
}

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

cleanup_on_exit() {
  local slot_path="$1" ticket_key="$2"
  _log INFO "Cleaning up slot for $ticket_key"

  # Remove orphan agent worktrees
  git -C "$slot_path" worktree list 2>/dev/null | grep -E '\.claude/worktrees|worktree-' | while read -r wt_line; do
    local wt_path; wt_path="$(echo "$wt_line" | awk '{print $1}')"
    _log INFO "Removing orphan worktree: $wt_path"
    git -C "$slot_path" worktree remove --force "$wt_path" 2>/dev/null || true
  done
  git -C "$slot_path" worktree prune 2>/dev/null || true

  pool_release "$slot_path" || _log WARN "Failed to release slot for $ticket_key"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

process_ticket() {
  local ticket_key="$1"
  local start_time; start_time="$(date +%s)"

  # Setup logging
  mkdir -p "$AUTOMATION_DIR/logs"
  local log_file="$AUTOMATION_DIR/logs/${ticket_key}-$(date +%Y%m%d-%H%M%S).log"
  exec > >(tee -a "$log_file") 2>&1

  _log INFO "Processing ticket $ticket_key"

  # Claim slot
  local slot_path claim_exit=0
  slot_path="$(pool_claim "$ticket_key")" || claim_exit=$?
  if [ "$claim_exit" -ne 0 ]; then
    if [ "$claim_exit" -eq 3 ]; then
      _log WARN "No slots available for $ticket_key, will retry next poll"
      exit 3
    fi
    _log ERROR "Failed to claim slot for $ticket_key"
    exit 1
  fi

  # Register cleanup trap
  trap 'cleanup_on_exit "$slot_path" "$ticket_key"' EXIT

  # Claim ticket (non-fatal)
  backend_claim_ticket "$ticket_key"

  # Fetch full ticket details
  local ticket_json
  ticket_json="$(backend_get_ticket "$ticket_key")" || {
    _log ERROR "Failed to fetch ticket $ticket_key"
    backend_fail_ticket "$ticket_key" "1" "Could not fetch ticket details" "0"
    exit 1
  }

  # Reset slot to latest origin/main
  pool_reset_slot "$slot_path" || {
    _log ERROR "Failed to reset slot for $ticket_key"
    backend_fail_ticket "$ticket_key" "1" "Could not reset worktree" "0"
    exit 1
  }

  # Create feature branch
  local summary; summary="$(echo "$ticket_json" | jq -r '.summary // ""')"
  local slug; slug="$(slugify_summary "$summary")"
  local safe_key="${ticket_key#\#}"
  local branch_name="feat/${safe_key}-${slug}"

  (cd "$slot_path" && git checkout -b "$branch_name") || {
    _log ERROR "Failed to create branch $branch_name"
    backend_fail_ticket "$ticket_key" "1" "Could not create branch" "0"
    exit 1
  }
  _log INFO "Created branch $branch_name"

  # Render prompt
  local prompt
  prompt="$(render_prompt "$ticket_key" "$ticket_json" "$branch_name")"
  _log INFO "Rendered prompt for $ticket_key (${#prompt} chars)"

  # Run Claude
  export CLAUDE_PIPELINE_MODE=autonomous
  local claude_stderr_file="$log_file.claude-stderr"
  local claude_exit=0
  local claude_output
  claude_output="$(cd "$slot_path" && claude -p "$prompt" \
    --output-format json \
    --permission-mode dontAsk \
    --max-budget-usd "$BUDGET_CAP" \
    --name "${TICKET_BACKEND}-${ticket_key#\#}" \
    --no-session-persistence \
    --teammate-mode in-process \
    $CLAUDE_EXTRA_FLAGS \
    2>"$claude_stderr_file")" || claude_exit=$?

  local end_time; end_time="$(date +%s)"
  local duration=$(( end_time - start_time ))

  # Handle Claude failure
  if [ "$claude_exit" -ne 0 ]; then
    local stderr_tail; stderr_tail="$(tail -20 "$claude_stderr_file" 2>/dev/null || echo "No stderr captured")"
    _log ERROR "Claude exited with code $claude_exit for $ticket_key"
    backend_fail_ticket "$ticket_key" "$claude_exit" "$stderr_tail" "$duration"
    exit 1
  fi

  # Parse Claude JSON output
  local session_id cost result_text
  session_id="$(echo "$claude_output" | jq -r '.session_id // ""')"
  cost="$(echo "$claude_output" | jq -r '.total_cost_usd // "0"')"
  result_text="$(echo "$claude_output" | jq -r '.result // ""')"

  _log INFO "Claude completed for $ticket_key (session=$session_id, cost=\$$cost, duration=${duration}s)"

  # Extract PR URL
  local pr_url; pr_url="$(extract_pr_url "$result_text" "$branch_name" "$slot_path")"

  if [ -n "$pr_url" ]; then
    backend_complete_ticket "$ticket_key" "$pr_url" "$cost" "$duration"
    _log INFO "Ticket $ticket_key completed: $pr_url"
  else
    # Check for verdict patterns indicating known failure modes
    if echo "$result_text" | grep -qE 'VERDICT:\s*(DECOMPOSE_REQUIRED|PIPELINE_FAILED)'; then
      local verdict; verdict="$(echo "$result_text" | grep -oE 'VERDICT:\s*(DECOMPOSE_REQUIRED|PIPELINE_FAILED)' | head -1)"
      _log WARN "Ticket $ticket_key ended with $verdict"
      backend_fail_ticket "$ticket_key" "1" "$verdict" "$duration"
    else
      _log WARN "No PR URL found for $ticket_key"
      backend_fail_ticket "$ticket_key" "1" "No PR created" "$duration"
    fi
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Entry point (when run directly, not sourced)
# ---------------------------------------------------------------------------

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [ $# -lt 1 ]; then
    echo "Usage: $0 <ticket-key>" >&2
    exit 2
  fi
  process_ticket "$1"
fi
