# Ticket Automation

Autonomous ticket processing — a daemon polls a tracker for ready tickets, runs the full
pipeline on each, opens a PR, and updates the ticket. Supports **Jira** and **GitHub Issues**
through a pluggable backend.

## Architecture

```
daemon.sh            polling loop (one per repo)
  backend.sh         dispatcher — loads jira.sh or github.sh from config
    jira.sh          Jira REST API (transitions, comments, ADF)
    github.sh        GitHub Issues via gh CLI (labels, comments)
  pool.sh            worktree pool (3 slots, atomic claiming, stale-lock recovery)
  process-ticket.sh  per-ticket: claim slot → run pipeline → update tracker
  prompt-template.md  backend-neutral Claude prompt
```

## Quick start

```bash
# 1. Per-repo config
cat > /path/to/your-repo/.claude/automation.env << 'EOF'
TICKET_BACKEND=github          # or "jira"

# --- GitHub Issues ---
GH_OWNER=your-org
GH_REPO=your-repo
GH_READY_LABEL=ready-for-dev   # issues with this label get picked up
GH_IN_PROGRESS_LABEL=in-progress
GH_DONE_LABEL=done
GH_BLOCKED_LABEL=blocked
GH_BOT_ACCOUNT=                # optional: assign issues to this account

# --- OR Jira ---
# JIRA_BASE_URL=https://your-org.atlassian.net
# JIRA_USER_EMAIL=bot@your-org.com
# JIRA_PROJECT_KEY=PROJ
# JIRA_READY_STATUS=Ready for Dev
# JIRA_IN_PROGRESS_STATUS=In Progress
# JIRA_DONE_STATUS=Done
# JIRA_FAILED_STATUS=Blocked
# JIRA_AC_CUSTOM_FIELD=         # custom field ID for acceptance criteria
# JIRA_BOT_ACCOUNT_ID=          # optional: for @mention
EOF

# 2. Secrets (Jira only — GitHub uses gh auth)
export JIRA_API_TOKEN=your-token   # only if TICKET_BACKEND=jira

# 3. Start / check / stop
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh start
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh status
REPO_PATH=/path/to/your-repo ~/.claude/automation/daemon.sh stop
```

## GitHub Issues setup

1. **Auth** — run `gh auth login` (the daemon uses your gh auth).
2. **Labels** — create these in your repo (names are configurable):
   `ready-for-dev` (pick up), `in-progress` (working), `done` (PR created), `blocked` (failed).
3. **Workflow** — add `ready-for-dev` → daemon picks it up → creates PR → closes issue with the PR link.
4. **AC format** — put acceptance criteria under a `## Acceptance Criteria` heading in the issue body (optional, improves quality).

## Jira setup

1. **API token** — generate at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. **Statuses** — set `JIRA_READY_STATUS` etc. to match your workflow.
3. **AC field** — if you use a custom field, set `JIRA_AC_CUSTOM_FIELD` to its ID (e.g. `customfield_10042`).
4. **Workflow** — move a ticket to "Ready for Dev" → daemon picks it up → creates PR → moves to "Done".

## Config hierarchy

```
~/.claude/automation/default.env     ← global defaults (all repos)
/path/to/repo/.claude/automation.env ← per-repo overrides
Environment variables                ← highest priority
```

## Daemon options

| Variable | Default | Purpose |
|----------|---------|---------|
| `TICKET_BACKEND` | `jira` | `jira` or `github` |
| `POOL_SIZE` | `3` | Parallel worktree slots |
| `BUDGET_CAP` | `10.00` | Max USD per ticket |
| `POLL_INTERVAL` | `60` | Seconds between polls |
| `SHUTDOWN_TIMEOUT` | `300` | Graceful-shutdown wait (seconds) |
| `MAX_TICKET_DURATION` | `3600` | Max seconds per ticket |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `CLAUDE_MODEL` | (default) | Override Claude model |
| `CLAUDE_EXTRA_FLAGS` | (none) | Extra flags passed to the `claude` CLI |

## Multi-repo (autonomous)

A single supervisor manages every repo's daemon:

```bash
# Register repos (one-time, or auto-registered by /harness:project-setup)
~/.claude/automation/supervisor.sh add /path/to/api-service
~/.claude/automation/supervisor.sh add /path/to/web-frontend

~/.claude/automation/supervisor.sh start          # start all registered daemons
~/.claude/automation/supervisor.sh status         # check everything
~/.claude/automation/supervisor.sh logs api-service
~/.claude/automation/supervisor.sh stop           # stop everything
```

The supervisor:

- **Auto-starts on session start** when repos are registered (via `session-start-bootstrap.sh`).
- Reads `repos.conf` (the single source of truth for registered repos).
- Starts a daemon per repo that has `.claude/automation.env`.
- Health-checks every 30s; auto-restarts crashed daemons (max 3/hour).
- Hot-reloads `repos.conf` — add/remove repos without restarting.
- Cascades graceful shutdown to all managed daemons.

Repos are auto-registered when `/harness:project-setup` creates an `automation.env`, or on
session start if the current repo already has one.
