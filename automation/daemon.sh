#!/usr/bin/env bash
# daemon.sh -- Polling daemon: watches Jira for ready tickets, dispatches processing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/pool.sh"
source "$SCRIPT_DIR/jira.sh"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PIDFILE="$AUTOMATION_DIR/daemon.pid"
ACTIVE_DIR="$AUTOMATION_DIR/.active-tickets"

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

daemon_start() {
  # Single-instance guard
  if [ -f "$PIDFILE" ]; then
    local existing_pid; existing_pid="$(cat "$PIDFILE")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      _log ERROR "Daemon already running (PID $existing_pid)"
      exit 1
    fi
    _log WARN "Removing stale PID file (PID $existing_pid is dead)"
    rm -f "$PIDFILE"
  fi

  # Write PID file
  echo "$$" > "$PIDFILE"

  # Register signal handlers
  trap 'daemon_shutdown' SIGTERM SIGINT SIGHUP
  trap 'rm -f "$PIDFILE"' EXIT

  mkdir -p "$ACTIVE_DIR" "$AUTOMATION_DIR/logs"

  _log INFO "Daemon starting (PID $$)"

  # Pre-flight checks
  _validate_config || { _log ERROR "Configuration validation failed"; exit 1; }
  jira_health_check || { _log ERROR "Jira health check failed"; exit 1; }
  pool_init || { _log ERROR "Pool initialization failed"; exit 1; }
  pool_recover

  _log INFO "Daemon ready (poll_interval=${POLL_INTERVAL}s, pool_size=${POOL_SIZE})"

  # Main loop
  while true; do
    poll_cycle
    sleep "$POLL_INTERVAL"
  done
}

# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------

poll_cycle() {
  reap_completed

  local active_count; active_count="$(ls "$ACTIVE_DIR" 2>/dev/null | wc -l | tr -d ' ')"
  local available=$(( POOL_SIZE - active_count ))

  if [ "$available" -le 0 ]; then
    _log DEBUG "All slots busy ($active_count/$POOL_SIZE)"
    return 0
  fi

  local tickets_json
  tickets_json="$(jira_poll_ready_tickets "$available")" || {
    _log WARN "Failed to poll Jira for ready tickets"
    return 0
  }

  local ticket_count; ticket_count="$(echo "$tickets_json" | jq -r '.total // 0')"
  if [ "$ticket_count" -eq 0 ]; then
    return 0
  fi

  _log INFO "Found $ticket_count ready ticket(s)"

  local dispatched=0
  local ticket_keys; ticket_keys="$(echo "$tickets_json" | jq -r '.issues[].key')"

  while IFS= read -r ticket_key; do
    [ -z "$ticket_key" ] && continue
    [ "$dispatched" -ge "$available" ] && break

    # Skip if already being processed
    if [ -f "$ACTIVE_DIR/$ticket_key" ]; then
      _log DEBUG "Skipping $ticket_key (already active)"
      continue
    fi

    # Launch in background
    ( "$SCRIPT_DIR/process-ticket.sh" "$ticket_key" ) &
    local child_pid=$!
    echo "$child_pid" > "$ACTIVE_DIR/$ticket_key"

    _log INFO "Dispatched $ticket_key (PID $child_pid)"
    dispatched=$((dispatched + 1))
  done <<< "$ticket_keys"
}

# ---------------------------------------------------------------------------
# Reaper -- collect finished background jobs
# ---------------------------------------------------------------------------

reap_completed() {
  local active_file
  for active_file in "$ACTIVE_DIR"/*; do
    [ -e "$active_file" ] || continue

    local ticket_key; ticket_key="$(basename "$active_file")"
    local child_pid; child_pid="$(cat "$active_file" 2>/dev/null || echo "")"

    [ -z "$child_pid" ] && { rm -f "$active_file"; continue; }

    # Check if process is still alive
    if kill -0 "$child_pid" 2>/dev/null; then
      continue
    fi

    # Process is dead -- collect exit status
    local exit_status=0
    wait "$child_pid" 2>/dev/null || exit_status=$?

    if [ "$exit_status" -eq 0 ]; then
      _log INFO "Ticket $ticket_key completed successfully (PID $child_pid)"
    elif [ "$exit_status" -eq 3 ]; then
      _log WARN "Ticket $ticket_key deferred -- no slots available (PID $child_pid)"
    else
      _log WARN "Ticket $ticket_key failed with exit code $exit_status (PID $child_pid)"
    fi

    rm -f "$active_file"
  done
}

# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------

daemon_shutdown() {
  _log INFO "Shutdown signal received"

  # Send SIGTERM to all active ticket processes
  local active_file
  for active_file in "$ACTIVE_DIR"/*; do
    [ -e "$active_file" ] || continue
    local child_pid; child_pid="$(cat "$active_file" 2>/dev/null || echo "")"
    if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
      _log INFO "Sending SIGTERM to PID $child_pid ($(basename "$active_file"))"
      kill -TERM "$child_pid" 2>/dev/null || true
    fi
  done

  # Wait for graceful shutdown with timeout
  local elapsed=0
  while [ "$elapsed" -lt "$SHUTDOWN_TIMEOUT" ]; do
    reap_completed
    local remaining; remaining="$(ls "$ACTIVE_DIR" 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$remaining" -eq 0 ]; then
      break
    fi
    _log INFO "Waiting for $remaining active ticket(s) to finish ($elapsed/${SHUTDOWN_TIMEOUT}s)"
    sleep 2
    elapsed=$((elapsed + 2))
  done

  # Force-kill any remaining
  for active_file in "$ACTIVE_DIR"/*; do
    [ -e "$active_file" ] || continue
    local child_pid; child_pid="$(cat "$active_file" 2>/dev/null || echo "")"
    if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
      _log WARN "Force-killing PID $child_pid ($(basename "$active_file"))"
      kill -KILL "$child_pid" 2>/dev/null || true
    fi
    rm -f "$active_file"
  done

  pool_recover
  _log INFO "Daemon stopped"
  exit 0
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

daemon_status() {
  if [ -f "$PIDFILE" ]; then
    local pid; pid="$(cat "$PIDFILE")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Daemon is running (PID $pid)"
      echo ""
      pool_status
      echo ""
      local active_count; active_count="$(ls "$ACTIVE_DIR" 2>/dev/null | wc -l | tr -d ' ')"
      echo "Active tickets: $active_count"
      if [ "$active_count" -gt 0 ]; then
        for active_file in "$ACTIVE_DIR"/*; do
          [ -e "$active_file" ] || continue
          local ticket; ticket="$(basename "$active_file")"
          local pid_val; pid_val="$(cat "$active_file" 2>/dev/null || echo "?")"
          echo "  $ticket (PID $pid_val)"
        done
      fi
    else
      echo "Daemon is not running (stale PID file for PID $pid)"
    fi
  else
    echo "Daemon is not running"
  fi
}

# ---------------------------------------------------------------------------
# Entry point (CLI)
# ---------------------------------------------------------------------------

case "${1:-start}" in
  start)   daemon_start ;;
  stop)    [ -f "$PIDFILE" ] && kill -TERM "$(cat "$PIDFILE")" || echo "Not running" ;;
  status)  daemon_status ;;
  recover) source "$SCRIPT_DIR/pool.sh"; pool_recover ;;
  *)       echo "Usage: $0 {start|stop|status|recover}" >&2; exit 1 ;;
esac
