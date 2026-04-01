#!/usr/bin/env bash
# config.sh -- Central configuration for Jira automation
# Sourced by other scripts. Does NOT use set -e (callers control error handling).

# ---------------------------------------------------------------------------
# Env file loading (per-repo config)
# ---------------------------------------------------------------------------
# Load order: global defaults -> repo-specific overrides -> env vars (highest priority)
# Global:  ~/.claude/automation/default.env
# Per-repo: $REPO_PATH/.claude/automation.env (or pass AUTOMATION_ENV=/path/to/file)
_load_env_file() {
  local f="$1"
  if [ -f "$f" ]; then
    # Source the file, but only export lines matching VAR=VALUE (skip comments/blanks)
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
}

_load_env_file "$HOME/.claude/automation/default.env"
[ -n "${AUTOMATION_ENV:-}" ] && _load_env_file "$AUTOMATION_ENV"
[ -n "${REPO_PATH:-}" ] && _load_env_file "$REPO_PATH/.claude/automation.env"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
AUTOMATION_DIR="${AUTOMATION_DIR:-$HOME/.claude/automation}"
REPO_PATH="${REPO_PATH:-}"
POOL_DIR="${POOL_DIR:-$REPO_PATH/.tickets}"

# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------
POOL_SIZE="${POOL_SIZE:-3}"

# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------
BUDGET_CAP="${BUDGET_CAP:-10.00}"
CLAUDE_MODEL="${CLAUDE_MODEL:-}"
CLAUDE_EXTRA_FLAGS="${CLAUDE_EXTRA_FLAGS:-}"
CLAUDE_PIPELINE_MODE="${CLAUDE_PIPELINE_MODE:-interactive}"

# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------
JIRA_BASE_URL="${JIRA_BASE_URL:-}"
JIRA_USER_EMAIL="${JIRA_USER_EMAIL:-}"
JIRA_API_TOKEN_VAR="${JIRA_API_TOKEN_VAR:-JIRA_API_TOKEN}"
JIRA_PROJECT_KEY="${JIRA_PROJECT_KEY:-}"
JIRA_READY_STATUS="${JIRA_READY_STATUS:-Ready for Dev}"
JIRA_IN_PROGRESS_STATUS="${JIRA_IN_PROGRESS_STATUS:-In Progress}"
JIRA_DONE_STATUS="${JIRA_DONE_STATUS:-Done}"
JIRA_FAILED_STATUS="${JIRA_FAILED_STATUS:-Blocked}"
JIRA_AC_CUSTOM_FIELD="${JIRA_AC_CUSTOM_FIELD:-}"
JIRA_BOT_ACCOUNT_ID="${JIRA_BOT_ACCOUNT_ID:-}"

# ---------------------------------------------------------------------------
# Backend Selection
# ---------------------------------------------------------------------------
TICKET_BACKEND="${TICKET_BACKEND:-jira}"

# ---------------------------------------------------------------------------
# GitHub Issues
# ---------------------------------------------------------------------------
GH_OWNER="${GH_OWNER:-}"
GH_REPO="${GH_REPO:-}"
GH_READY_LABEL="${GH_READY_LABEL:-ready-for-dev}"
GH_IN_PROGRESS_LABEL="${GH_IN_PROGRESS_LABEL:-in-progress}"
GH_DONE_LABEL="${GH_DONE_LABEL:-done}"
GH_BLOCKED_LABEL="${GH_BLOCKED_LABEL:-blocked}"
GH_BOT_ACCOUNT="${GH_BOT_ACCOUNT:-}"

# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------
POLL_INTERVAL="${POLL_INTERVAL:-60}"
SHUTDOWN_TIMEOUT="${SHUTDOWN_TIMEOUT:-300}"
MAX_TICKET_DURATION="${MAX_TICKET_DURATION:-3600}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
_validate_config() {
  local error_count=0

  if [ -z "${REPO_PATH:-}" ]; then
    echo "ERROR: REPO_PATH is required but empty" >&2
    error_count=$((error_count + 1))
  fi

  case "$TICKET_BACKEND" in
    jira)
      local required_vars="JIRA_BASE_URL JIRA_USER_EMAIL JIRA_PROJECT_KEY"
      for var_name in $required_vars; do
        if [ -z "${!var_name}" ]; then
          echo "ERROR: $var_name is required for Jira backend" >&2
          error_count=$((error_count + 1))
        fi
      done
      if [ -z "${!JIRA_API_TOKEN_VAR:-}" ]; then
        echo "ERROR: env var \$$JIRA_API_TOKEN_VAR is not set" >&2
        error_count=$((error_count + 1))
      fi
      ;;
    github)
      for var_name in GH_OWNER GH_REPO; do
        if [ -z "${!var_name}" ]; then
          echo "ERROR: $var_name is required for GitHub backend" >&2
          error_count=$((error_count + 1))
        fi
      done
      ;;
    *)
      echo "ERROR: Unknown TICKET_BACKEND '$TICKET_BACKEND' (expected 'jira' or 'github')" >&2
      error_count=$((error_count + 1))
      ;;
  esac

  if [ -n "$REPO_PATH" ] && [ ! -d "$REPO_PATH/.git" ]; then
    echo "ERROR: REPO_PATH ($REPO_PATH) is not a git repository" >&2
    error_count=$((error_count + 1))
  fi

  local required_tools="claude gh jq"
  [ "$TICKET_BACKEND" = "jira" ] && required_tools+=" curl"
  for tool in $required_tools; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      echo "ERROR: required tool '$tool' not found in PATH" >&2
      error_count=$((error_count + 1))
    fi
  done

  return "$error_count"
}
