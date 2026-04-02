#!/usr/bin/env bash
# supervisor.sh -- Manages per-repo ticket automation daemons from a single entry point
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_DIR="${SCRIPT_DIR}"
REPOS_CONF="${AUTOMATION_DIR}/repos.conf"
SUPERVISOR_PID_FILE="${AUTOMATION_DIR}/supervisor.pid"
SUPERVISOR_STATE_DIR="${AUTOMATION_DIR}/.supervisor"
LOG_DIR="${AUTOMATION_DIR}/logs"
LOG_FILE="${LOG_DIR}/supervisor.log"
HEALTH_CHECK_INTERVAL=30
MAX_RESTARTS_PER_HOUR=3

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_supervisor_log() {
    local level="$1"; shift
    mkdir -p "$LOG_DIR"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [supervisor] [$level] $*" >> "$LOG_FILE"
    echo "[$level] $*" >&2
}

# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------

_sanitize_path() {
    local raw="$1"
    echo "$raw" | sed 's|^/||' | sed 's|/|_|g'
}

_repo_name_from_path() {
    basename "$1"
}

# ---------------------------------------------------------------------------
# repos.conf reading
# ---------------------------------------------------------------------------

_read_repos_conf() {
    if [ ! -f "$REPOS_CONF" ]; then
        return 0
    fi
    grep -v '^\s*#' "$REPOS_CONF" \
        | grep -v '^\s*$' \
        | sed 's/^[[:space:]]*//' \
        | sed 's/[[:space:]]*$//'
}

# ---------------------------------------------------------------------------
# Repo validation
# ---------------------------------------------------------------------------

_validate_repo() {
    local repo_path="$1"
    if [ ! -d "$repo_path" ]; then
        _supervisor_log WARN "Repo path does not exist: $repo_path"
        return 1
    fi
    if [ ! -d "$repo_path/.git" ]; then
        _supervisor_log WARN "Not a git repository: $repo_path"
        return 1
    fi
    if [ ! -f "$repo_path/.claude/automation.env" ]; then
        _supervisor_log WARN "Missing .claude/automation.env: $repo_path"
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Per-repo daemon management
# ---------------------------------------------------------------------------

_daemon_pid_file() {
    local repo_path="$1"
    local sanitized; sanitized="$(_sanitize_path "$repo_path")"
    echo "${SUPERVISOR_STATE_DIR}/${sanitized}.pid"
}

_is_daemon_running() {
    local pid_file="$1"
    if [ ! -f "$pid_file" ]; then
        return 1
    fi
    local pid; pid="$(cat "$pid_file")"
    if [ -z "$pid" ]; then
        return 1
    fi
    kill -0 "$pid" 2>/dev/null
}

_start_repo_daemon() {
    local repo_path="$1"
    local pid_file; pid_file="$(_daemon_pid_file "$repo_path")"
    local repo_name; repo_name="$(_repo_name_from_path "$repo_path")"
    local repo_log="${LOG_DIR}/${repo_name}.log"

    if _is_daemon_running "$pid_file"; then
        _supervisor_log INFO "Daemon already running for $repo_name"
        return 0
    fi

    _supervisor_log INFO "Starting daemon for $repo_name ($repo_path)"
    REPO_PATH="$repo_path" \
        nohup bash "$SCRIPT_DIR/daemon.sh" start \
        >> "$repo_log" 2>&1 &
    local daemon_pid=$!
    echo "$daemon_pid" > "$pid_file"
    _supervisor_log INFO "Daemon started for $repo_name (PID $daemon_pid)"
}

_stop_repo_daemon() {
    local repo_path="$1"
    local pid_file; pid_file="$(_daemon_pid_file "$repo_path")"
    local repo_name; repo_name="$(_repo_name_from_path "$repo_path")"

    if ! _is_daemon_running "$pid_file"; then
        _supervisor_log INFO "Daemon not running for $repo_name"
        rm -f "$pid_file"
        return 0
    fi

    local pid; pid="$(cat "$pid_file")"
    _supervisor_log INFO "Stopping daemon for $repo_name (PID $pid)"
    kill -TERM "$pid" 2>/dev/null || true

    local elapsed=0
    while [ "$elapsed" -lt 30 ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        _supervisor_log WARN "Force-killing daemon for $repo_name (PID $pid)"
        kill -KILL "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    _supervisor_log INFO "Daemon stopped for $repo_name"
}

# ---------------------------------------------------------------------------
# Restart tracking
# ---------------------------------------------------------------------------

_restart_count_file() {
    local repo_path="$1"
    local sanitized; sanitized="$(_sanitize_path "$repo_path")"
    echo "${SUPERVISOR_STATE_DIR}/${sanitized}.restarts"
}

_record_restart() {
    local repo_path="$1"
    local count_file; count_file="$(_restart_count_file "$repo_path")"
    local now; now="$(date +%s)"
    echo "$now" >> "$count_file"
}

_restart_count_within_hour() {
    local repo_path="$1"
    local count_file; count_file="$(_restart_count_file "$repo_path")"
    if [ ! -f "$count_file" ]; then
        echo 0
        return
    fi
    local one_hour_ago; one_hour_ago="$(( $(date +%s) - 3600 ))"
    local count=0
    while IFS= read -r timestamp; do
        if [ "$timestamp" -ge "$one_hour_ago" ] 2>/dev/null; then
            count=$((count + 1))
        fi
    done < "$count_file"
    echo "$count"
}

_prune_old_restarts() {
    local repo_path="$1"
    local count_file; count_file="$(_restart_count_file "$repo_path")"
    if [ ! -f "$count_file" ]; then
        return
    fi
    local one_hour_ago; one_hour_ago="$(( $(date +%s) - 3600 ))"
    local temp_file="${count_file}.tmp"
    while IFS= read -r timestamp; do
        if [ "$timestamp" -ge "$one_hour_ago" ] 2>/dev/null; then
            echo "$timestamp"
        fi
    done < "$count_file" > "$temp_file"
    mv "$temp_file" "$count_file"
}

# ---------------------------------------------------------------------------
# Failed repo tracking
# ---------------------------------------------------------------------------

_failed_marker_file() {
    local repo_path="$1"
    local sanitized; sanitized="$(_sanitize_path "$repo_path")"
    echo "${SUPERVISOR_STATE_DIR}/${sanitized}.failed"
}

_mark_repo_failed() {
    local repo_path="$1"
    touch "$(_failed_marker_file "$repo_path")"
}

_is_repo_failed() {
    local repo_path="$1"
    [ -f "$(_failed_marker_file "$repo_path")" ]
}

_clear_repo_failed() {
    local repo_path="$1"
    rm -f "$(_failed_marker_file "$repo_path")"
}

# ---------------------------------------------------------------------------
# Health check loop
# ---------------------------------------------------------------------------

_health_check() {
    local repos_conf_mtime_file="${SUPERVISOR_STATE_DIR}/repos_conf_mtime"
    local current_mtime; current_mtime="$(stat -f %m "$REPOS_CONF" 2>/dev/null || echo 0)"
    local stored_mtime="0"

    if [ -f "$repos_conf_mtime_file" ]; then
        stored_mtime="$(cat "$repos_conf_mtime_file")"
    fi

    if [ "$current_mtime" != "$stored_mtime" ]; then
        _supervisor_log INFO "repos.conf changed, reconciling daemons"
        _reconcile_daemons
        echo "$current_mtime" > "$repos_conf_mtime_file"
    fi

    _check_daemon_health
}

_check_daemon_health() {
    local repo_path
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        local pid_file; pid_file="$(_daemon_pid_file "$repo_path")"
        local repo_name; repo_name="$(_repo_name_from_path "$repo_path")"

        if _is_repo_failed "$repo_path"; then
            continue
        fi

        if ! _is_daemon_running "$pid_file"; then
            _supervisor_log WARN "Daemon died for $repo_name, attempting restart"
            _prune_old_restarts "$repo_path"
            local restart_count; restart_count="$(_restart_count_within_hour "$repo_path")"

            if [ "$restart_count" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
                _supervisor_log ERROR "Daemon for $repo_name exceeded $MAX_RESTARTS_PER_HOUR restarts/hour, marking failed"
                _mark_repo_failed "$repo_path"
                continue
            fi

            _record_restart "$repo_path"
            rm -f "$pid_file"
            _start_repo_daemon "$repo_path"
        fi
    done < <(_read_repos_conf)
}

_reconcile_daemons() {
    local desired_repos=()
    local repo_path
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        desired_repos+=("$repo_path")
    done < <(_read_repos_conf)

    # Start daemons for new repos
    for repo_path in "${desired_repos[@]}"; do
        if ! _validate_repo "$repo_path"; then
            continue
        fi
        _clear_repo_failed "$repo_path"
        local pid_file; pid_file="$(_daemon_pid_file "$repo_path")"
        if ! _is_daemon_running "$pid_file"; then
            _start_repo_daemon "$repo_path"
        fi
    done

    # Stop daemons for removed repos
    for pid_file in "$SUPERVISOR_STATE_DIR"/*.pid; do
        [ -e "$pid_file" ] || continue
        local sanitized_name; sanitized_name="$(basename "$pid_file" .pid)"
        local found=false
        for repo_path in "${desired_repos[@]}"; do
            local check_sanitized; check_sanitized="$(_sanitize_path "$repo_path")"
            if [ "$sanitized_name" = "$check_sanitized" ]; then
                found=true
                break
            fi
        done
        if [ "$found" = false ]; then
            local stale_pid; stale_pid="$(cat "$pid_file" 2>/dev/null || echo "")"
            if [ -n "$stale_pid" ] && kill -0 "$stale_pid" 2>/dev/null; then
                _supervisor_log INFO "Stopping removed repo daemon (PID $stale_pid)"
                kill -TERM "$stale_pid" 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done
}

# ---------------------------------------------------------------------------
# Supervisor lifecycle
# ---------------------------------------------------------------------------

supervisor_start() {
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        local existing_pid; existing_pid="$(cat "$SUPERVISOR_PID_FILE")"
        if kill -0 "$existing_pid" 2>/dev/null; then
            _supervisor_log ERROR "Supervisor already running (PID $existing_pid)"
            exit 1
        fi
        _supervisor_log WARN "Removing stale supervisor PID file (PID $existing_pid)"
        rm -f "$SUPERVISOR_PID_FILE"
    fi

    mkdir -p "$SUPERVISOR_STATE_DIR" "$LOG_DIR"
    echo "$$" > "$SUPERVISOR_PID_FILE"

    trap 'supervisor_shutdown' SIGTERM SIGINT
    trap '_on_sighup' SIGHUP
    trap 'rm -f "$SUPERVISOR_PID_FILE"' EXIT

    _supervisor_log INFO "Supervisor starting (PID $$)"

    # Initial startup: validate and launch all registered repo daemons
    local repo_count=0
    local repo_path
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        if _validate_repo "$repo_path"; then
            _start_repo_daemon "$repo_path"
            repo_count=$((repo_count + 1))
        fi
    done < <(_read_repos_conf)

    _supervisor_log INFO "Supervisor ready ($repo_count repo daemon(s) started)"

    # Store initial repos.conf mtime
    local mtime_file="${SUPERVISOR_STATE_DIR}/repos_conf_mtime"
    stat -f %m "$REPOS_CONF" 2>/dev/null > "$mtime_file" || echo 0 > "$mtime_file"

    # Health check loop
    while true; do
        sleep "$HEALTH_CHECK_INTERVAL"
        _health_check
    done
}

supervisor_shutdown() {
    _supervisor_log INFO "Supervisor shutdown signal received"

    local repo_path
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        _stop_repo_daemon "$repo_path"
    done < <(_read_repos_conf)

    # Also stop any daemons tracked in state but not in conf
    for pid_file in "$SUPERVISOR_STATE_DIR"/*.pid; do
        [ -e "$pid_file" ] || continue
        local pid; pid="$(cat "$pid_file" 2>/dev/null || echo "")"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
    done

    _supervisor_log INFO "Supervisor stopped"
    exit 0
}

_on_sighup() {
    _supervisor_log INFO "SIGHUP received, reconciling daemons"
    _reconcile_daemons
    local mtime_file="${SUPERVISOR_STATE_DIR}/repos_conf_mtime"
    stat -f %m "$REPOS_CONF" 2>/dev/null > "$mtime_file" || echo 0 > "$mtime_file"
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

supervisor_status() {
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        local pid; pid="$(cat "$SUPERVISOR_PID_FILE")"
        if kill -0 "$pid" 2>/dev/null; then
            echo "Supervisor: running (PID $pid)"
        else
            echo "Supervisor: not running (stale PID file for $pid)"
        fi
    else
        echo "Supervisor: not running"
    fi

    echo ""
    echo "Registered repos:"

    if [ ! -f "$REPOS_CONF" ]; then
        echo "  (no repos.conf found)"
        return
    fi

    local repo_path
    local has_repos=false
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        has_repos=true
        local repo_name; repo_name="$(_repo_name_from_path "$repo_path")"
        local pid_file; pid_file="$(_daemon_pid_file "$repo_path")"
        local status="stopped"

        if _is_repo_failed "$repo_path"; then
            status="failed (exceeded restart limit)"
        elif _is_daemon_running "$pid_file"; then
            local pid; pid="$(cat "$pid_file")"
            status="running (PID $pid)"
        fi

        echo "  $repo_name: $status"
        echo "    path: $repo_path"
    done < <(_read_repos_conf)

    if [ "$has_repos" = false ]; then
        echo "  (none)"
    fi
}

# ---------------------------------------------------------------------------
# Add / Remove repos
# ---------------------------------------------------------------------------

supervisor_add() {
    local repo_path="$1"

    # Resolve to absolute path
    if [[ "$repo_path" != /* ]]; then
        repo_path="$(cd "$repo_path" 2>/dev/null && pwd)"
    fi
    # Remove trailing slash
    repo_path="${repo_path%/}"

    if ! _validate_repo "$repo_path"; then
        echo "ERROR: Invalid repo: $repo_path" >&2
        echo "Repo must exist, be a git repository, and have .claude/automation.env" >&2
        exit 1
    fi

    # Create repos.conf if missing
    if [ ! -f "$REPOS_CONF" ]; then
        cat > "$REPOS_CONF" << 'HEADER'
# repos.conf -- Registered repositories for ticket automation
# One absolute path per line. Repos must have .claude/automation.env
# Add repos: supervisor.sh add /path/to/repo
# Remove repos: supervisor.sh remove /path/to/repo
# Auto-registered by /project-setup when automation.env is created
HEADER
    fi

    # Deduplicate
    if grep -qxF "$repo_path" "$REPOS_CONF" 2>/dev/null; then
        echo "Repo already registered: $repo_path"
        return 0
    fi

    echo "$repo_path" >> "$REPOS_CONF"
    echo "Added: $repo_path"

    # Signal supervisor to re-read if running
    _signal_supervisor_reload
}

supervisor_remove() {
    local repo_path="$1"

    # Resolve to absolute path
    if [[ "$repo_path" != /* ]]; then
        repo_path="$(cd "$repo_path" 2>/dev/null && pwd)"
    fi
    repo_path="${repo_path%/}"

    if [ ! -f "$REPOS_CONF" ]; then
        echo "No repos.conf found" >&2
        exit 1
    fi

    if ! grep -qxF "$repo_path" "$REPOS_CONF" 2>/dev/null; then
        echo "Repo not registered: $repo_path" >&2
        exit 1
    fi

    # Remove the line (exact match)
    local temp_file="${REPOS_CONF}.tmp"
    grep -vxF "$repo_path" "$REPOS_CONF" > "$temp_file"
    mv "$temp_file" "$REPOS_CONF"
    echo "Removed: $repo_path"

    # Stop daemon if supervisor is running
    if _is_supervisor_running; then
        _stop_repo_daemon "$repo_path"
    fi

    _signal_supervisor_reload
}

# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------

supervisor_restart() {
    _supervisor_log INFO "Restart requested"

    # Stop all daemons
    local repo_path
    for pid_file in "$SUPERVISOR_STATE_DIR"/*.pid; do
        [ -e "$pid_file" ] || continue
        local pid; pid="$(cat "$pid_file" 2>/dev/null || echo "")"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
    done

    # Clear failed markers
    rm -f "$SUPERVISOR_STATE_DIR"/*.failed
    rm -f "$SUPERVISOR_STATE_DIR"/*.restarts

    # Wait briefly for daemons to stop
    sleep 2

    # Re-read and start
    local repo_count=0
    while IFS= read -r repo_path; do
        [ -z "$repo_path" ] && continue
        if _validate_repo "$repo_path"; then
            _start_repo_daemon "$repo_path"
            repo_count=$((repo_count + 1))
        fi
    done < <(_read_repos_conf)

    _supervisor_log INFO "Restart complete ($repo_count daemon(s) started)"
    echo "Restarted $repo_count daemon(s)"
}

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

supervisor_logs() {
    local target="${1:-}"

    if [ -z "$target" ]; then
        # Tail supervisor log
        if [ -f "$LOG_FILE" ]; then
            tail -50 "$LOG_FILE"
        else
            echo "No supervisor log found"
        fi
        return
    fi

    # Find matching repo log
    local log_file="${LOG_DIR}/${target}.log"
    if [ -f "$log_file" ]; then
        tail -50 "$log_file"
    else
        echo "No log found for '$target'" >&2
        echo "Available logs:" >&2
        for f in "$LOG_DIR"/*.log; do
            [ -e "$f" ] || continue
            echo "  $(basename "$f" .log)" >&2
        done
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_is_supervisor_running() {
    if [ ! -f "$SUPERVISOR_PID_FILE" ]; then
        return 1
    fi
    local pid; pid="$(cat "$SUPERVISOR_PID_FILE")"
    kill -0 "$pid" 2>/dev/null
}

_signal_supervisor_reload() {
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        local pid; pid="$(cat "$SUPERVISOR_PID_FILE")"
        if kill -0 "$pid" 2>/dev/null; then
            kill -HUP "$pid" 2>/dev/null || true
        fi
    fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

case "${1:-}" in
    start)   supervisor_start ;;
    stop)
        if _is_supervisor_running; then
            kill -TERM "$(cat "$SUPERVISOR_PID_FILE")"
            echo "Supervisor stop signal sent"
        else
            echo "Supervisor is not running"
        fi
        ;;
    status)  supervisor_status ;;
    add)
        [ -z "${2:-}" ] && { echo "Usage: $0 add /path/to/repo" >&2; exit 1; }
        supervisor_add "$2"
        ;;
    remove)
        [ -z "${2:-}" ] && { echo "Usage: $0 remove /path/to/repo" >&2; exit 1; }
        supervisor_remove "$2"
        ;;
    restart)
        if _is_supervisor_running; then
            supervisor_restart
        else
            echo "Supervisor is not running. Use 'start' instead." >&2
            exit 1
        fi
        ;;
    logs)
        supervisor_logs "${2:-}"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|add|remove|restart|logs}" >&2
        echo "" >&2
        echo "Commands:" >&2
        echo "  start              Start supervisor and all registered repo daemons" >&2
        echo "  stop               Stop all daemons and supervisor" >&2
        echo "  status             Show supervisor and per-repo daemon status" >&2
        echo "  add /path/to/repo  Register a repo and start its daemon" >&2
        echo "  remove /path/to/repo  Unregister a repo and stop its daemon" >&2
        echo "  restart            Restart all daemons (re-reads repos.conf)" >&2
        echo "  logs [repo-name]   Tail logs (supervisor or specific repo)" >&2
        exit 1
        ;;
esac
