# Enterprise Rollout

How this harness gets onto engineer Macs via the Claude Code plugin system.

> **Why this is not a vanilla `github` marketplace.** Claude Code's built-in plugin
> installer cannot clone this marketplace from a `github` source: the repo is **private**
> *and* named `.claude` (leading dot). Its bundled git fails the clone (`Marketplace file
> not found …/Adviser-Group--claude/.claude-plugin/marketplace.json`), and a
> `strictKnownMarketplaces` `github` matcher cannot match the dot-named repo either. The
> rollout therefore clones the repo with **system git** and registers it as a **local
> directory marketplace**. If Anthropic fixes private/dot-name cloning, this can revert to
> a plain `github` source + a two-line bootstrap.

## Administrator setup (one-time)

Paste the contents of `managed-settings.json` into the Anthropic enterprise console's
managed-settings section. It configures:

- `enabledPlugins` — force-enables `harness@adviser-group`.
- `hooks.SessionStart` — clones the repo with **system git** into
  `~/.claude/local-marketplaces/adviser-group`, registers it as a **local** marketplace,
  and installs the plugin. (The explicit install covers CLI gap #45323 — `enabledPlugins`
  alone does not trigger a CLI install.)
- `hooks.PreToolUse` — a nudge that fires on Edit/Write if the harness is absent.
- `env`, `permissions`, `claudeMd` — org-wide operational config, destructive-op deny
  rules, and doctrine.

Do **not**, for this repo:
- add an `extraKnownMarketplaces` entry with a `github` source — it triggers the failing
  native clone (and the `adviser-group (managed) — Marketplace file not found` error);
- set `strictKnownMarketplaces` — its `github` matcher does not match the `.claude`
  dot-name and blocks the marketplace (`not in the allowed marketplace list`).

Do not commit secrets into `managed-settings.json`.

## How installation works

1. The enterprise console pushes `managed-settings.json` to every engineer.
2. On session start the `SessionStart` hook (backgrounded, non-blocking):
   - resolves a GitHub token: `GITHUB_TOKEN` → `GH_TOKEN` → `gh auth token`;
   - clones (or `git pull`s) `Adviser-Group/.claude` with **system git** into
     `~/.claude/local-marketplaces/adviser-group` — the token is injected per-command and
     then stripped from the stored remote, so it is never persisted to `.git/config`;
   - `claude plugin marketplace add <that directory>` (a **directory** source);
   - `claude plugin install harness@adviser-group`.
3. Subsequent sessions `git pull` to update, then exit silently (idempotent — guarded by
   `~/.claude/.adviser-harness-installed`).
4. If the harness is still absent at `PreToolUse` time, a nudge fires (see
   Self-remediation).

Logs: `~/.claude/logs/harness-bootstrap.log`.

## Engineer onboarding (one-time)

Authenticate the GitHub CLI so the hook can clone the private repo:

```bash
gh auth login
```

Choose GitHub.com and complete the web/device flow with the account that has read access
to `Adviser-Group/.claude`. That is the **only** per-engineer step — no SSH config, no
`extraKnownMarketplaces`, no shared token, and `gh auth setup-git` is not required (the
bootstrap injects the token into the clone URL directly).

On first session start Claude Code shows a **one-time security-approval prompt** for the
managed-settings policy (it introduces hooks + env). Approve it.

## Verification

```bash
claude plugin list                              # harness@adviser-group → enabled
claude plugin details harness@adviser-group
```

Expected:

```
Status: ✔ enabled        Version: 1.1.0
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
D="$HOME/.claude/local-marketplaces/adviser-group"
git clone https://github.com/Adviser-Group/.claude.git "$D"   # system git, uses your gh creds
claude plugin marketplace add "$D"
claude plugin install harness@adviser-group
# then restart Claude Code
```

> **Do not** run `claude plugin marketplace add Adviser-Group/.claude` (the github
> shorthand) — Claude Code's bundled git cannot clone this private, dot-named repo. Always
> add the **local directory** path.

One-off bypass of the nudge for a single session: `export ADVISER_HARNESS_OPT_OUT=1` then
restart.

## Rollback

Per machine:

```bash
claude plugin uninstall harness@adviser-group
claude plugin marketplace remove adviser-group
rm -rf "$HOME/.claude/local-marketplaces/adviser-group"   # optional: drop the local clone
```

Org-wide: remove `harness@adviser-group` from `enabledPlugins` in the console (and/or
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

## Out of scope

- Claude Desktop / claude.ai — does not read `~/.claude/` or the plugin store.
- Claude Code cloud runners — ephemeral; use repo-level `CLAUDE.md` + `.mcp.json` per
  project.

## Troubleshooting

**`Marketplace file not found …/Adviser-Group--claude/.claude-plugin/marketplace.json`**
The native `github` clone failed (expected for this repo). Use the local-directory method
— it is the default in the shipped `managed-settings.json`; for a manual fix see
Self-remediation.

**`Marketplace "adviser-group" is not in the allowed marketplace list`**
`strictKnownMarketplaces` is set and its matcher does not match this repo. Remove
`strictKnownMarketplaces` from managed-settings.

**`could not read Username` / permission denied during clone**
`gh auth status` must show an authenticated account with read access to
`Adviser-Group/.claude`. Run `gh auth login`.

**Plugin fails to load: `Duplicate hooks file detected`**
`plugin.json` must NOT declare `"hooks": "./hooks/hooks.json"` — the standard
`hooks/hooks.json` is auto-loaded. Fixed in v1.1.0+.

**`MCP servers (0)` in `plugin details`**
The servers must live in `.mcp.json` at the plugin root (not inline in `plugin.json`).
Fixed in v1.1.0+.

**`CLAUDE_PLUGIN_ROOT` empty**
Only set inside plugin contexts. If a skill/hook cannot resolve it, the plugin failed to
load — check `claude plugin list` for a load error and the bootstrap log.
