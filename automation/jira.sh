#!/usr/bin/env bash
# jira.sh -- Jira REST API wrapper for automation
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Logging fallback (pool.sh may define _log before sourcing this)
if ! declare -f _log >/dev/null 2>&1; then
  _log() { local level="$1"; shift; echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] [$level] $*" >&2; }
fi

# --- Auth -------------------------------------------------------------------

_jira_auth_header() {
  local token="${!JIRA_API_TOKEN_VAR:-}"
  if [ -z "$token" ]; then
    _log ERROR "Jira API token not set in \$$JIRA_API_TOKEN_VAR"; return 1
  fi
  printf '%s' "$JIRA_USER_EMAIL:$token" | base64
}

# --- Internal helpers -------------------------------------------------------

_is_retryable_status() { [ "$1" = "429" ] || [ "$1" -ge 500 ] 2>/dev/null; }

_parse_http_status() {
  [ -f "$1" ] \
    && grep -oE 'HTTP/[0-9.]+ [0-9]+' "$1" | tail -1 | grep -oE '[0-9]+$' \
    || echo "0"
}

_parse_retry_after() {
  local header_file="$1" default="$2"
  if [ -f "$header_file" ]; then
    local val
    val="$(grep -i 'retry-after' "$header_file" | head -1 | grep -oE '[0-9]+' || echo "")"
    if [ -n "$val" ] && [ "$val" -gt 0 ] 2>/dev/null; then echo "$val"; return; fi
  fi
  echo "$default"
}

_url_encode() { jq -rn --arg val "$1" '$val | @uri'; }

_html_to_text() {
  printf '%s' "$1" \
    | sed 's/<br[^>]*>/\n/g; s/<\/p>/\n/g; s/<[^>]*>//g' \
    | sed 's/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g; s/&quot;/"/g; s/&nbsp;/ /g' \
    | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
    | sed '/^$/N;/^\n$/d'
}

_build_adf_paragraphs() {
  jq -n --arg t "$1" '
    ($t | split("\n")) as $lines |
    {body:{type:"doc",version:1,content:[
      $lines[] | select(length > 0) |
      {type:"paragraph",content:[{type:"text",text:.}]}
    ]}}'
}

# --- Retry wrapper ----------------------------------------------------------

_jira_request() {
  local method="$1" endpoint="$2" body="${3:-}"
  local auth_header
  auth_header="$(_jira_auth_header)" || return 1
  local url="${JIRA_BASE_URL}${endpoint}"
  local max_attempts=3 attempt=1 backoff=1

  while [ "$attempt" -le "$max_attempts" ]; do
    local tmp_headers; tmp_headers="$(mktemp)"
    local curl_args=(
      --request "$method" --max-time 30 --silent --show-error
      --header "Authorization: Basic $auth_header"
      --header "Content-Type: application/json"
      --header "Accept: application/json"
      --dump-header "$tmp_headers"
    )
    [ -n "$body" ] && curl_args+=(--data "$body")
    curl_args+=("$url")

    local response; response="$(curl "${curl_args[@]}" 2>&1)" || true
    local http_status; http_status="$(_parse_http_status "$tmp_headers")"
    local retry_after_val; retry_after_val="$(_parse_retry_after "$tmp_headers" "$backoff")"
    rm -f "$tmp_headers"
    JIRA_LAST_HTTP_STATUS="$http_status"

    if [ "$http_status" -ge 200 ] 2>/dev/null && [ "$http_status" -lt 300 ] 2>/dev/null; then
      echo "$response"; return 0
    fi

    if _is_retryable_status "$http_status"; then
      _log WARN "Jira $method $endpoint HTTP $http_status (attempt $attempt/$max_attempts)"
      [ "$http_status" = "429" ] && backoff="$retry_after_val"
      [ "$attempt" -lt "$max_attempts" ] && sleep "$backoff" && backoff=$((backoff * 2))
      attempt=$((attempt + 1)); continue
    fi

    _log ERROR "Jira API $method $endpoint failed: HTTP $http_status"; return 1
  done

  _log ERROR "Jira API $method $endpoint failed after $max_attempts attempts"; return 1
}

# --- Public functions -------------------------------------------------------

jira_health_check() {
  local response
  response="$(_jira_request GET /rest/api/3/myself)" || {
    local status="${JIRA_LAST_HTTP_STATUS:-0}"
    if [ "$status" -ge 400 ] 2>/dev/null && [ "$status" -lt 500 ] 2>/dev/null; then
      _log ERROR "Jira authentication failed (HTTP $status)"; return 1
    fi
    _log ERROR "Jira unreachable"; return 2
  }
  _log INFO "Jira authenticated as: $(echo "$response" | jq -r '.displayName // "unknown"')"
  return 0
}

jira_poll_ready_tickets() {
  local limit="${1:-$POOL_SIZE}"
  local jql="project = $JIRA_PROJECT_KEY AND status = \"$JIRA_READY_STATUS\""
  jql+=" ORDER BY priority DESC, created ASC"
  local encoded_jql; encoded_jql="$(_url_encode "$jql")"
  local fields="key,summary,issuetype,priority,components,labels"
  local endpoint="/rest/api/3/search?jql=$encoded_jql&maxResults=$limit&fields=$fields"

  local response
  response="$(_jira_request GET "$endpoint")" || { _log ERROR "Failed to poll ready tickets"; return 1; }
  echo "$response"
}

jira_get_ticket() {
  local ticket_key="${1:-}"
  if [ -z "$ticket_key" ]; then
    _log ERROR "jira_get_ticket: ticket_key is required"; return 2
  fi
  local fields="key,summary,description,issuetype,priority,components,labels,parent"
  [ -n "${JIRA_AC_CUSTOM_FIELD:-}" ] && fields+=",$JIRA_AC_CUSTOM_FIELD"
  local endpoint="/rest/api/3/issue/$ticket_key?expand=renderedFields&fields=$fields"

  local response
  response="$(_jira_request GET "$endpoint")" || {
    local status="${JIRA_LAST_HTTP_STATUS:-0}"
    if [ "$status" = "404" ]; then _log ERROR "Ticket $ticket_key not found"; return 1; fi
    _log ERROR "Failed to fetch ticket $ticket_key (HTTP $status)"; return 2
  }
  echo "$response"
}

jira_transition() {
  local ticket_key="${1:-}" target_status_name="${2:-}"
  if [ -z "$ticket_key" ] || [ -z "$target_status_name" ]; then
    _log ERROR "jira_transition: ticket_key and target_status_name required"; return 2
  fi

  local transitions_response
  transitions_response="$(_jira_request GET "/rest/api/3/issue/$ticket_key/transitions")" || {
    _log ERROR "Failed to fetch transitions for $ticket_key"; return 2
  }

  local transition_id
  transition_id="$(echo "$transitions_response" \
    | jq -r --arg name "$target_status_name" '.transitions[] | select(.name == $name) | .id' \
    | head -1)"
  if [ -z "$transition_id" ]; then
    _log ERROR "Transition '$target_status_name' not available for $ticket_key"; return 1
  fi

  local body; body="$(jq -n --arg id "$transition_id" '{transition:{id:$id}}')"
  _jira_request POST "/rest/api/3/issue/$ticket_key/transitions" "$body" >/dev/null || {
    _log ERROR "Failed to transition $ticket_key to '$target_status_name'"; return 2
  }
  _log INFO "Transitioned $ticket_key to '$target_status_name'"
}

jira_add_comment() {
  local ticket_key="${1:-}" comment_text="${2:-}"
  if [ -z "$ticket_key" ] || [ -z "$comment_text" ]; then
    _log ERROR "jira_add_comment: ticket_key and comment_text required"; return 1
  fi
  local adf_body; adf_body="$(_build_adf_paragraphs "$comment_text")"
  _jira_request POST "/rest/api/3/issue/$ticket_key/comment" "$adf_body" >/dev/null || {
    _log ERROR "Failed to add comment to $ticket_key"; return 1
  }
  _log INFO "Added comment to $ticket_key"
}

jira_add_rich_comment() {
  local ticket_key="${1:-}" adf_json="${2:-}"
  if [ -z "$ticket_key" ] || [ -z "$adf_json" ]; then
    _log ERROR "jira_add_rich_comment: ticket_key and adf_json required"; return 1
  fi
  _jira_request POST "/rest/api/3/issue/$ticket_key/comment" "$adf_json" >/dev/null || {
    _log ERROR "Failed to add rich comment to $ticket_key"; return 1
  }
  _log INFO "Added rich comment to $ticket_key"
}

# --- Backend contract implementation -----------------------------------------

backend_health_check() { jira_health_check; }

backend_poll_ready_tickets() {
  local limit="${1:-$POOL_SIZE}"
  local response
  response="$(jira_poll_ready_tickets "$limit")" || return 1
  echo "$response" | jq '{tickets: [.issues[] | {key: .key, summary: .fields.summary}]}'
}

backend_get_ticket() {
  local ticket_key="$1"
  local response
  response="$(jira_get_ticket "$ticket_key")" || return $?
  local summary issue_type priority components labels parent_key
  summary="$(echo "$response" | jq -r '.fields.summary // ""')"
  issue_type="$(echo "$response" | jq -r '.fields.issuetype.name // ""')"
  priority="$(echo "$response" | jq -r '.fields.priority.name // ""')"
  components="$(echo "$response" | jq -r '[.fields.components[].name] | join(", ") // ""')"
  labels="$(echo "$response" | jq -r '[.fields.labels[]] | join(", ") // ""')"
  parent_key="$(echo "$response" | jq -r '.fields.parent.key // ""')"
  local raw_description description acceptance_criteria
  raw_description="$(echo "$response" | jq -r '.renderedFields.description // ""')"
  description="$(_html_to_text "$raw_description")"
  if [ -n "${JIRA_AC_CUSTOM_FIELD:-}" ]; then
    local raw_ac
    raw_ac="$(echo "$response" | jq -r ".renderedFields.${JIRA_AC_CUSTOM_FIELD} // \"\"")"
    acceptance_criteria="$(_html_to_text "$raw_ac")"
  else
    acceptance_criteria="Not specified"
  fi
  local url="${JIRA_BASE_URL}/browse/${ticket_key}"
  jq -n \
    --arg key "$ticket_key" \
    --arg summary "$summary" \
    --arg description "$description" \
    --arg issue_type "$issue_type" \
    --arg priority "$priority" \
    --arg components "$components" \
    --arg labels "$labels" \
    --arg parent_key "$parent_key" \
    --arg acceptance_criteria "$acceptance_criteria" \
    --arg url "$url" \
    --argjson raw "$response" \
    '{key:$key,summary:$summary,description:$description,
      issue_type:$issue_type,priority:$priority,components:$components,
      labels:$labels,parent_key:$parent_key,
      acceptance_criteria:$acceptance_criteria,url:$url,raw:$raw}'
}

backend_claim_ticket() {
  local ticket_key="$1"
  jira_transition "$ticket_key" "$JIRA_IN_PROGRESS_STATUS" || \
    _log WARN "Could not transition $ticket_key to $JIRA_IN_PROGRESS_STATUS"
  jira_add_comment "$ticket_key" "Claude automation started processing this ticket." || \
    _log WARN "Could not post start comment to $ticket_key"
}

backend_post_comment() {
  local ticket_key="$1" text="$2"
  jira_add_comment "$ticket_key" "$text"
}

backend_complete_ticket() {
  local ticket_key="$1" pr_url="$2" cost="$3" duration="$4"
  local comment
  comment="$(printf 'Claude automation completed successfully.\n\nPR: %s\nCost: $%s\nDuration: %s seconds' "$pr_url" "$cost" "$duration")"
  jira_add_comment "$ticket_key" "$comment" 2>/dev/null || true
  jira_transition "$ticket_key" "$JIRA_DONE_STATUS" 2>/dev/null || true
}

backend_fail_ticket() {
  local ticket_key="$1" exit_code="$2" stderr_tail="$3" duration="$4"
  local comment
  comment="$(printf 'Claude automation failed.\n\nExit code: %s\nDuration: %s seconds\n\nLast output:\n%s' "$exit_code" "$duration" "$stderr_tail")"
  jira_add_comment "$ticket_key" "$comment" 2>/dev/null || true
  jira_transition "$ticket_key" "$JIRA_FAILED_STATUS" 2>/dev/null || true
}

backend_ticket_url() {
  local ticket_key="$1"
  echo "${JIRA_BASE_URL}/browse/${ticket_key}"
}
