# Enterprise Rollout

How this harness gets onto engineer Macs via the Claude Code plugin system.

## Administrator setup (one-time)

Paste the contents of `managed-settings.json` into the Anthropic enterprise console's
managed-settings section for the organisation. This file configures:

- `enabledPlugins` — grants `harness@adviser-group` from the Adviser-Group private
  marketplace.
- `hooks` — the `SessionStart` entry that triggers plugin installation automatically.
- `permissions` — deny/allow rules applied to all engineers.

Do not commit secrets into `managed-settings.json`.

## How installation works

1. The enterprise console pushes `managed-settings.json` to every engineer's Claude Code
   install.
2. On first session start the `SessionStart` hook runs:
   ```bash
   claude plugin marketplace add Adviser-Group/.claude
   claude plugin install harness@adviser-group
   ```
   The two-step sequence is required because the CLI does not auto-install plugins that
   become available via a newly added marketplace entry (CLI gap #45323 — install step
   remains explicit until that is resolved).
3. If the plugin is already installed the hook exits silently.
4. If the plugin is absent at `PreToolUse` time a nudge fires reminding the engineer to
   run the manual install command (see Self-Remediation below).

## Engineer onboarding (one-time)

Before the first Claude Code session, every engineer must authenticate the GitHub CLI so
the hook can reach the private Adviser-Group marketplace:

```bash
gh auth login
```

Choose GitHub.com → HTTPS → "Login with a web browser" and complete the device-flow
prompt.

On first session start Claude Code will show a **one-time security-approval prompt** for
the managed-settings policy. Review and approve it to allow the hooks and plugin to
activate.

## Verification

After the first session completes, confirm the plugin is active:

```bash
claude plugin list
```

Expected: `harness@adviser-group` appears with status `enabled`.

For a detailed view:

```bash
claude plugin details harness@adviser-group
```

Expected output includes:
```
Hooks: 14
Skills: 65
Agents: 19
```

Inside a Claude Code session you can also run:

- `/status` — shows active hooks and loaded skills
- `/permissions` — shows the deny/allow policy in effect

## Self-remediation

If the plugin did not install (e.g. `gh auth` was incomplete, or the session started
before the managed-settings push landed):

1. Authenticate the GitHub CLI if not already done: `gh auth login`
2. Add the marketplace manually:
   ```bash
   claude plugin marketplace add Adviser-Group/.claude
   ```
3. Install the plugin:
   ```bash
   claude plugin install harness@adviser-group
   ```
4. Restart Claude Code.

The `PreToolUse` nudge hook will remind you with the exact commands if it detects the
plugin is absent at tool-call time.

## Rollback

To remove the harness plugin from an engineer's machine:

```bash
claude plugin uninstall harness@adviser-group
claude plugin marketplace remove adviser-group
```

To remove it org-wide, edit the enterprise console and remove `harness@adviser-group`
from `enabledPlugins` in the managed-settings. The `SessionStart` hook will no longer
install it on subsequent sessions.

## Out of scope

- Claude Desktop app (`claude.ai`) — does not read `~/.claude/` or the plugin store.
- Claude Code cloud runners — ephemeral containers. Use repo-level `CLAUDE.md` +
  `.mcp.json` in each project instead.

## Troubleshooting

**Plugin not found after install**

Check that `CLAUDE_PLUGIN_ROOT` is resolving correctly:

```bash
echo $CLAUDE_PLUGIN_ROOT
```

This variable must point to the directory where the harness was installed. If it is
empty, Claude Code did not set it — file a support ticket or check the managed-settings
`pluginDataDir` field.

**Permission denied during install**

Ensure `gh auth status` shows an authenticated session for the account that has read
access to `Adviser-Group/.claude`.

**Hook fires but plugin keeps reinstalling**

The session-start hook is idempotent. If it reinstalls on every session the version pin
in `version-pin` may be drifting — check `claude plugin details harness@adviser-group`
and compare the version with the pinned value.
