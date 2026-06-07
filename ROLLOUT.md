# Enterprise Rollout

> **After every merge to `main`:** re-paste `templates/org-defaults/managed-settings.json`
> into the Anthropic enterprise console → Managed Settings. The console distributes the
> updated bootstrap to all engineers automatically — no per-engineer action needed.
> See [§ How updates propagate](#how-updates-propagate).

How this harness gets onto engineer Macs via the Claude Code plugin system.

> **Why this is not a vanilla `github` marketplace.** Claude Code's built-in plugin
> installer cannot clone this marketplace from a `github` source: the repo is **private**
> *and* named `.claude` (leading dot). Its bundled git fails the clone (`Marketplace file
> not found …/paulingham--claude/.claude-plugin/marketplace.json`), and a
> `strictKnownMarketplaces` `github` matcher cannot match the dot-named repo either. The
> rollout therefore clones the repo with **system git** and registers it as a **local
> directory marketplace**. If Anthropic fixes private/dot-name cloning, this can revert to
> a plain `github` source + a two-line bootstrap.

## Administrator setup (one-time)

Paste the contents of `managed-settings.json` into the Anthropic enterprise console's
managed-settings section. It configures:

- `enabledPlugins` — force-enables `harness@paulingham`.
- `hooks.SessionStart` — clones the repo with **system git** into
  `~/.claude/local-marketplaces/paulingham`, registers it as a **local** marketplace,
  and installs the plugin. (The explicit install covers CLI gap #45323 — `enabledPlugins`
  alone does not trigger a CLI install.)
- `hooks.PreToolUse` — a nudge that fires on Edit/Write if the harness is absent.
- `env`, `permissions`, `claudeMd` — org-wide operational config, destructive-op deny
  rules, and doctrine.

Do **not**, for this repo:
- add an `extraKnownMarketplaces` entry with a `github` source — it triggers the failing
  native clone (and the `paulingham (managed) — Marketplace file not found` error);
- set `strictKnownMarketplaces` — its `github` matcher does not match the `.claude`
  dot-name and blocks the marketplace (`not in the allowed marketplace list`).

Do not commit secrets into `managed-settings.json`.

## Server-managed settings console JSON

Use `templates/org-defaults/managed-settings.json` as the authoritative source to paste
into the Anthropic enterprise console → Managed Settings.

> **Template location**: `templates/org-defaults/managed-settings.json` is the canonical
> version. The JSON below annotates the key fields. See `templates/org-defaults/README.md`
> for the promotion path to `paulingham/org-defaults`.

### Field-by-field reference

The console JSON is a standard Claude Code settings document. Key fields:

```json
{
  // Force-enables the harness plugin for all engineers in the org.
  // This triggers the CLI gap workaround (enabledPlugins alone does not
  // install on CLI — the SessionStart hook handles the actual install).
  "enabledPlugins": { "harness@paulingham": true },

  // Org-wide env vars injected into every Claude Code session.
  // These control harness behaviour: hook profile, subagent limits, trace off.
  "env": {
    "CLAUDE_HOOK_PROFILE": "standard",
    "CLAUDE_PIPELINE_MODE": "autonomous",
    "CLAUDE_ENABLE_TRACE": "0"
    // ... see managed-settings.json for the full list
  },

  // Destructive-op deny rules — protect main branches, prevent data loss.
  "permissions": {
    "deny": [ /* git push --force, rm -rf, etc */ ]
  },

  // Org doctrine injected into every session's system prompt.
  // Points engineers to the harness pipeline entry point.
  "claudeMd": "# Personal Harness — Doctrine (managed) ...",

  "hooks": {
    // SessionStart: on every session, clone or update the harness repo using
    // system git + a GitHub token, register it as a local-directory marketplace,
    // and install the plugin. Runs backgrounded (non-blocking). Idempotent:
    // guarded by ~/.claude/.harness-installed sentinel.
    // NOTE: requires gh auth login (one-time per engineer) — see Known Limitations.
    "SessionStart": [ { "matcher": "startup|resume", "hooks": [ { "type": "command", "command": "<bootstrap-command>" } ] } ],

    // PreToolUse: if the harness is still absent at Edit/Write time, fire a
    // nudge directing the engineer to run gh auth login and restart.
    "PreToolUse": [ { "matcher": "Edit|Write", "hooks": [ { "type": "command", "command": "<nudge-command>" } ] } ]
  }
}
```

For the exact command strings, copy directly from `templates/org-defaults/managed-settings.json`.

### Staged rollout sequence

Roll out in two stages to catch issues before org-wide deployment.

**Stage 1 — Test cohort** (5-10 volunteer engineers):

1. In the Anthropic enterprise console, apply `managed-settings.json` to a test-cohort
   policy group only (not the full org).
2. Ask cohort engineers to restart Claude Code and approve the one-time security prompt.
3. Verify on each cohort machine:

   ```bash
   claude plugin list | grep harness@paulingham
   ```

   Expected output: `harness@paulingham → enabled`

4. If the plugin does not appear:
   - Check `~/.claude/logs/harness-bootstrap.log` for the error.
   - Common cause: `gh auth login` not completed — run it and restart.
   - See the Troubleshooting section below.

**Stage 2 — Org-wide** (after cohort confirms):

1. Expand the console policy from the test-cohort group to the full engineering org.
2. Communicate the `gh auth login` prerequisite to all engineers (one-time step).
3. Spot-check a sample of machines:

   ```bash
   claude plugin list | grep harness@paulingham
   ```

### Known limitations (managed-settings path)

- **Desktop gap**: Claude Desktop does not read the enterprise console managed-settings
  policy. Engineers on Desktop are not covered by this rollout. See `templates/org-defaults/README.md`.
- **Cloud-runner gap**: A cloud runner without the harness repo committed to its project
  cannot run the bootstrap. `enabledPlugins` alone is inert on cloud without a registered
  marketplace. See `templates/org-defaults/README.md` for cloud coverage options.
- **gh auth login prerequisite**: The bootstrap hard-depends on `gh auth login` having been
  completed. The `PreToolUse` nudge fires at the next `Edit`/`Write` call if the harness
  is absent — but the nudge does not fire before the first edit. Engineers must run
  `gh auth login` once before the bootstrap succeeds.

## How updates propagate

The harness uses **SHA-based versioning**: the installed plugin version is the git commit
SHA of the `~/.claude/local-marketplaces/paulingham` clone, not an explicit version
string in `plugin.json`. This means:

- Every merge to `main` in `paulingham/.claude` is immediately a new version.
- No manual version bump in `plugin.json` is needed or permitted.
- On each session start the bootstrap runs `git pull` (advancing the clone's HEAD SHA)
  then `claude plugin marketplace update paulingham` + `claude plugin update harness@paulingham`,
  which re-syncs the plugin cache to the new SHA.
- **Rollback**: revert the commit on `main` — the next session start syncs to the revert SHA.
- **Admin action required after each release**: re-paste `templates/org-defaults/managed-settings.json`
  into the Anthropic enterprise console → Managed Settings. Without this step, engineers on
  the old bootstrap will `git pull` new code but never call `plugin update`, leaving their
  cache frozen.

The security of this mechanism depends on `main` being branch-protected (required PR reviews,
no direct pushes) — a compromise of `main` is equivalent to org-wide code execution on next
restart.

Logs: `~/.claude/logs/harness-bootstrap.log`. If engineers report stale harness despite
restarts, check the log for `plugin marketplace update` and `plugin update` lines. If those
lines are absent or show a CLI error, the `claude` binary may be too old — upgrade Claude
Code CLI on the affected machine.

## How installation works

1. The enterprise console pushes `managed-settings.json` to every engineer.
2. On session start the `SessionStart` hook (backgrounded, non-blocking):
   - resolves a GitHub token: `GITHUB_TOKEN` → `GH_TOKEN` → `gh auth token`;
   - clones (or `git pull`s) `paulingham/.claude` with **system git** into
     `~/.claude/local-marketplaces/paulingham` — the token is injected per-command and
     then stripped from the stored remote, so it is never persisted to `.git/config`;
   - `claude plugin marketplace add <that directory>` (a **directory** source);
   - `claude plugin install harness@paulingham`.
3. Subsequent sessions `git pull` to update, then run `claude plugin marketplace update` and
   `claude plugin update harness@paulingham` to sync the plugin cache, then exit silently
   (idempotent — guarded by `~/.claude/.harness-installed`).
4. If the harness is still absent at `PreToolUse` time, a nudge fires (see
   Self-remediation).

Logs: `~/.claude/logs/harness-bootstrap.log`.

## Engineer onboarding (one-time)

Authenticate the GitHub CLI so the hook can clone the private repo:

```bash
gh auth login
```

Choose GitHub.com and complete the web/device flow with the account that has read access
to `paulingham/.claude`. That is the **only** per-engineer step — no SSH config, no
`extraKnownMarketplaces`, no shared token, and `gh auth setup-git` is not required (the
bootstrap injects the token into the clone URL directly).

On first session start Claude Code shows a **one-time security-approval prompt** for the
managed-settings policy (it introduces hooks + env). Approve it.

## Verification

```bash
claude plugin list                              # harness@paulingham → enabled
claude plugin details harness@paulingham
```

Expected:

```
Status: ✔ enabled        Version: <commit-sha>
Skills (65)  Agents (19)  Hooks (14)  MCP servers (4)
```

The 4 MCP servers are `gh-cache`, `memory`, `lsp-typescript`, `lsp-pyright`.

> `/reload-plugins` reports a much smaller "skills" number — that counter does not include
> SKILL.md-based plugin skills. `claude plugin details` is authoritative (65).

## Self-remediation

If the harness did not install (e.g. `gh auth` incomplete, or the session started before
the policy landed):

```bash
gh auth login
D="$HOME/.claude/local-marketplaces/paulingham"
git clone https://github.com/paulingham/.claude.git "$D"   # system git, uses your gh creds
claude plugin marketplace add "$D"
claude plugin install harness@paulingham
# then restart Claude Code
```

> **Do not** run `claude plugin marketplace add paulingham/.claude` (the github
> shorthand) — Claude Code's bundled git cannot clone this private, dot-named repo. Always
> add the **local directory** path.

One-off bypass of the nudge for a single session: `export HARNESS_OPT_OUT=1` then
restart.

## Rollback

Per machine:

```bash
claude plugin uninstall harness@paulingham
claude plugin marketplace remove paulingham
rm -rf "$HOME/.claude/local-marketplaces/paulingham"   # optional: drop the local clone
```

Org-wide: remove `harness@paulingham` from `enabledPlugins` in the console (and/or
remove the `SessionStart` hook). The bootstrap will no longer install on subsequent
sessions.

## Known limitations

- **Native `github`/SSH plugin clone is unsupported for this repo** (private + dot-name).
  Worked around via system-git + local directory marketplace. Worth a Claude Code bug
  report; if fixed, revert to a plain `github` source.
- **`.mcp.json` is committed (force-added past `.gitignore`)** so the 4 MCP servers ship
  with the plugin — only `.mcp.json` at the plugin root is parsed; inline `mcpServers` and
  the path-string form in `plugin.json` are **not**. Side effect: opening *this repo as a
  project* tries to start those servers with `${CLAUDE_PLUGIN_ROOT}` unset and shows them
  as failed. Harmless; affects only people working inside the harness repo itself.
- **`repository-created.yml` pushes directly to main** in newly created repos. Direct push
  is intentional — new repos have no branch protection rules. The security of this path
  rests entirely on `paulingham/org-defaults` repo integrity (restrict write access
  accordingly). If your org requires PRs for all repos, modify the workflow to open a PR.

## Out of scope

- Claude Desktop / claude.ai — does not read `~/.claude/` or the plugin store.
- Claude Code cloud runners — ephemeral; use repo-level `CLAUDE.md` + `.mcp.json` per
  project.

## Troubleshooting

**`Marketplace file not found …/paulingham--claude/.claude-plugin/marketplace.json`**
The native `github` clone failed (expected for this repo). Use the local-directory method
— it is the default in the shipped `managed-settings.json`; for a manual fix see
Self-remediation.

**`Marketplace "paulingham" is not in the allowed marketplace list`**
`strictKnownMarketplaces` is set and its matcher does not match this repo. Remove
`strictKnownMarketplaces` from managed-settings.

**`could not read Username` / permission denied during clone**
`gh auth status` must show an authenticated account with read access to
`paulingham/.claude`. Run `gh auth login`.

**Plugin fails to load: `Duplicate hooks file detected`**
`plugin.json` must NOT declare `"hooks": "./hooks/hooks.json"` — the standard
`hooks/hooks.json` is auto-loaded. Fixed in v1.1.0+.

**`MCP servers (0)` in `plugin details`**
The servers must live in `.mcp.json` at the plugin root (not inline in `plugin.json`).
Fixed in v1.1.0+.

**`CLAUDE_PLUGIN_ROOT` empty**
Only set inside plugin contexts. If a skill/hook cannot resolve it, the plugin failed to
load — check `claude plugin list` for a load error and the bootstrap log.
