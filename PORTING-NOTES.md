# Porting Notes: overlay-sync → plugin

Reference document for maintainers porting this harness from the legacy
overlay-sync delivery model (direct git clone into `~/.claude/`) to the
Claude Code plugin system.

---

## (a) RTK omission rationale

The Redux Toolkit (`rtk`) package is not included in the plugin manifest.
The harness ships shell hooks, Python helpers, and Markdown skill files —
none of which require a JavaScript runtime toolkit. RTK was evaluated and
dropped because it would add a JS dependency tree with no benefit to the
current skill/hook surface. If the harness ever ships a browser-facing
dashboard component this decision should be revisited.

---

## (b) `bash -lc` login-shell behaviour

Several hooks invoke sub-shells via `bash -lc '...'` to ensure login
profiles (`~/.zshrc`, `~/.bash_profile`) load before reading `CLAUDE_PLUGIN_ROOT`.
In plugin mode `CLAUDE_PLUGIN_ROOT` is set by the Claude Code host process
and inherited by every hook invocation, so a login shell is not needed for
*that* variable. However, `bash -lc` is still used for hooks that need
`$NVM_DIR`, `$RBENV_ROOT`, or similar tool-version managers that are only
available after sourcing a login profile.

The key point: `CLAUDE_PLUGIN_ROOT` resolves from the inherited environment
regardless of whether the sub-shell is a login shell or not. The path is a
quoted, absolute string — no tilde expansion is required.

---

## (c) Sandbox-block exclusion

The Claude Code sandbox `allowOnly` list controls which filesystem paths
hooks may write to. A typical `allowOnly` for security-focused organisations
restricts writes to `~/.gnupg/`, `~/.ssh/`, and the `gh` credential store.

If the sandbox `allowOnly` is re-enabled, it **must** include:

```
$CLAUDE_PLUGIN_DATA/logs
$CLAUDE_PLUGIN_DATA/metrics
$CLAUDE_PLUGIN_DATA/pipeline-state
$CLAUDE_PLUGIN_DATA/session-memory
$CLAUDE_PLUGIN_DATA/learning
$CLAUDE_PLUGIN_DATA/agent-memory
```

Without these entries the harness will be unable to write observation logs,
session memory, and pipeline state — every hook that appends to those paths
will be silently blocked, causing `LEARNED`/`BUILD_COMPLETE`/`PIPELINE_COMPLETE`
verdicts to be lost.

The sandbox was excluded from the initial plugin port because adding these
paths safely requires auditing every hook's write surface first. Re-enable
only after that audit is complete.

---

## (d) Overlay-to-plugin maintainer migration

In overlay mode the harness repo lived at `~/.claude/` — the same directory
Claude Code reads as its config root (`CLAUDE_CONFIG_DIR`). In plugin mode
the harness is installed at `$CLAUDE_PLUGIN_ROOT` (a separate path chosen
by the Claude Code host, typically inside `~/.claude/plugins/`).

**Migration steps for a maintainer machine:**

1. Confirm the plugin is installed:
   ```bash
   claude plugin details harness@adviser-group
   ```
2. Move the old overlay checkout out of the config directory:
   ```bash
   mv ~/.claude ~/.claude-overlay-backup
   ```
3. Let Claude Code recreate a minimal `~/.claude/` on next launch (it
   writes `settings.json` and session state there).
4. Verify `CLAUDE_PLUGIN_ROOT` points to the plugin install, not the old
   overlay path:
   ```bash
   echo $CLAUDE_PLUGIN_ROOT
   # Expected: something like ~/.claude/plugins/harness@adviser-group/
   ```

If both the overlay checkout and the plugin are present simultaneously,
hooks and skills will load twice — once from each root — causing duplicate
verdicts and unpredictable behaviour. `harness-paths.sh` is idempotent: the
`_HARNESS_PATHS_LOADED` guard makes a second `source` a no-op (it returns
immediately), so double-sourcing the same file is harmless. The real
double-load risk is having two separate harness installs active at once —
the overlay checkout and the plugin each providing a full copy of hooks and
skills — which is why the maintainer must relocate the `~/.claude` checkout
out of the config directory (Step 2 above).

---

## (e) Auto-update story

The harness updates itself through two complementary mechanisms:

**Claude Code native autoupdate** — when `autoUpdate: true` is set in the
plugin manifest, Claude Code fetches and applies plugin updates automatically
on session start. This is the primary update path.

**Bootstrap daily marketplace update** — the `SessionStart` hook runs a
daily marketplace sync check:
```bash
claude plugin marketplace update adviser-group
```
This is throttled by a daily stamp so it does not add per-session latency.
The env var `KEEP_MARKETPLACE_ON_FAILURE=1` preserves the existing plugin
version if the marketplace is unreachable (network-gated environments).

**Note:** `FORCE_AUTOUPDATE_PLUGINS` is an undocumented internal flag and
is intentionally not documented or relied upon here. Do not use it in
operator runbooks — its semantics are subject to change without notice.

---

## (f) Multi-version `$CLAUDE_PLUGIN_DATA` isolation

Plugin data directories are namespaced by plugin identifier. If two
versions of the harness are installed simultaneously (e.g. during a
canary rollout), each version writes to its own `$CLAUDE_PLUGIN_DATA`
path:

```
~/.claude/plugin-data/harness@adviser-group/1.2.0/
~/.claude/plugin-data/harness@adviser-group/1.3.0-rc.1/
```

This isolation means:
- Pipeline state from one version is invisible to the other.
- `learning/` instincts are not shared between versions.
- Metrics and session memory are version-scoped.

To migrate accumulated instincts from one version to the next:
```bash
cp -r "$OLD_CLAUDE_PLUGIN_DATA/learning/" "$NEW_CLAUDE_PLUGIN_DATA/learning/"
```

Check `echo $CLAUDE_PLUGIN_DATA` inside an active session to confirm which
version's data directory is active.

---

## (g) `additionalDirectories` deferred (CA4)

The `additionalDirectories` array in `settings.json` (lines 71–84) lists paths
rooted at `"$HOME/.claude/…"`. Claude Code does **not** expand plugin vars
(`CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`) in the `additionalDirectories`
field — it reads these as literal strings. Replacing them with env-var
references would break the feature on all current installs.

This migration is **deferred** pending Claude Code adding plugin-var expansion
support for `additionalDirectories`. The workaround for plugin-mode installs:
ensure `$HOME/.claude` is symlinked to or equal to `$CLAUDE_PLUGIN_DATA` for
the relevant subdirectories. Until then, `additionalDirectories` paths remain
hardcoded to `$HOME/.claude` and are explicitly excluded from the
plugin-portability sweep.

---

## Troubleshooting

**`mcp_memory/SKILL.md:46` sample path**

The illustrative `.mcp.json` snippet in `skills/mcp_memory/SKILL.md` at
line 46 shows:

```json
"rootDir": "$HOME/.claude/db"
```

In plugin mode `$HOME/.claude` is the Claude Code config directory, not the
plugin install root. If the memory MCP server reads this path literally, it
will write to the config root's `db/` directory, not the plugin data
directory.

For plugin installs, update the path to:

```json
"rootDir": "${CLAUDE_PLUGIN_DATA:-$HOME/.claude}/db"
```

The sample in the SKILL.md is intentionally left as-is because it is an
illustrative snippet for users configuring their own `.mcp.json` — not
executable harness code.

**Corrupt plugin install**

If the plugin state is corrupt (missing files, broken hooks), reinstall:

```bash
claude plugin uninstall harness@adviser-group
claude plugin install harness@adviser-group
```

This performs a clean install without touching `$CLAUDE_PLUGIN_DATA`
(accumulated learning and pipeline state are preserved). If data corruption
is also suspected, additionally remove the data directory before reinstalling.
