# Enterprise Rollout

How this harness gets onto engineer Macs.

## Engineer onboarding (one-time)

Before launching Claude Code for the first time, every engineer must authenticate the GitHub CLI so the bootstrap can clone this private repo:

```bash
gh auth login
```

Choose GitHub.com → HTTPS → "Login with a web browser" and complete the device-flow prompt. Without this, the bootstrap silently no-ops and `~/.claude/` will not appear.

## What the rollout does

1. The Anthropic enterprise console pushes `managed-settings.json` to every engineer's Claude Code install.
2. On every Claude Code session start, a hook backgrounds a call to `bootstrap.sh` (fetched from this repo via `gh api`).
3. `bootstrap.sh` clones (or daily-pulls) this repo into `~/.claude/`. Any pre-existing `~/.claude/` is backed up to `~/.claude.bak.<timestamp>`.
4. Bootstrap is daily-throttled via `~/.claude/.harness-last-check`. Logs roll at `~/.claude/.bootstrap.log` (last 200 lines).
5. Bootstrap exits 0 on every failure path — a broken harness never blocks Claude Code from starting.

## Manual update

To force a refresh without waiting for the daily tick:

```bash
rm -f ~/.claude/.harness-last-check
bash ~/.claude/bootstrap.sh
```

## Files in this rollout

- `managed-settings.json` — paste contents into the Anthropic enterprise console's managed-settings section. Do not commit secrets here.
- `bootstrap.sh` — clone/update logic. Fetched by the SessionStart hook via `gh api`.

## Out of scope

- Claude Desktop app (`claude.ai`) — does not read `~/.claude/`.
- Claude Code cloud runners — ephemeral containers, do not read local files. Use repo-level `CLAUDE.md` + `.mcp.json` in each project instead.
