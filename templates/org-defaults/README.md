# templates/org-defaults

Canonical distribution scaffold for the Adviser Group Claude Code harness
(`harness@adviser-group`). These artifacts are the source of truth for
org-wide harness delivery; they are staged here before promotion.

## Promotion path

These files are destined for a standalone `Adviser-Group/org-defaults` repository.

**Promotion steps:**

1. Create `Adviser-Group/org-defaults` (if it doesn't exist).
2. Copy the contents of this directory into that repo's root.
3. Configure the org-level required-workflow ruleset to reference
   `.github/workflows/required-workflow-drift-check.yml` from `Adviser-Group/org-defaults`.
4. Set `ORG_SYNC_TOKEN` as an org-level secret with repo-read and pull-request-write access.
5. Run `.github/workflows/repo-file-sync.yml` manually to seed existing repos.
6. From that point on, pushes to `Adviser-Group/org-defaults` automatically sync
   canonical files to enrolled repos via `repo-file-sync.yml`.

## Contents

| File | Purpose |
|------|---------|
| `settings.json` | Repo-committed Claude Code config (cloud + local install, hook entry-points) |
| `managed-settings.json` | Enterprise console paste-in (server-managed policy for CLI/IDE engineers) |
| `.github/workflows/repo-file-sync.yml` | Syncs canonical files to org repos on push |
| `.github/workflows/repository-created.yml` | Seeds new repos with org defaults on creation |
| `.github/workflows/required-workflow-drift-check.yml` | Detects drift from org-defaults source |

## Using managed-settings.json (administrator setup)

1. Open the Anthropic enterprise console → Managed Settings.
2. Paste the full contents of `managed-settings.json` and save.
3. The console distributes the policy to all engineers on next session start.
4. Engineers need `gh auth login` (one-time) before the bootstrap runs — see prerequisite below.

## One-time engineer prerequisite: gh auth login

The `SessionStart` bootstrap uses **system git** to clone the harness repo with a GitHub
token. Before the first harness session, each engineer must authenticate:

```bash
gh auth login
```

Choose GitHub.com and complete the web/device flow with an account that has read access
to `Adviser-Group/.claude`. This is the **only** per-engineer step. Without it, the
bootstrap clone silently fails. At the next `Edit` or `Write` tool call, the `PreToolUse`
nudge fires to remind the engineer.

## Coverage gaps and known limitations

### Desktop gap

**Claude Desktop does not read `~/.claude/` or the plugin store.** Neither the enterprise
console managed-settings policy nor the repo-committed `settings.json` is picked up by
Claude Desktop. The harness is unavailable on Desktop until Anthropic ships console-to-Desktop
policy delivery. This gap is accepted (Discussion.md Option A); no workaround exists today.

### Cloud-runner gap (no committed repo)

A cloud runner (Claude Code on the web) that starts **without** the harness repo committed
to the cloud project cannot run `cloud-bootstrap.sh`. In this scenario `enabledPlugins` in
the repo-committed `settings.json` is inert because no marketplace entry is registered.

Coverage requires one of:
- The harness repo committed to the cloud project (`CLAUDE_PROJECT_DIR` set).
- A public mirror created (security decision, out of scope for this pipeline).
- Anthropic fixes bundled-git private/dot-name clone (not actionable by this team).

### No extraKnownMarketplaces github source

`extraKnownMarketplaces` with a `github` source is intentionally absent from both
`settings.json` and `managed-settings.json`. Claude Code's bundled git fails on the
private dot-named `Adviser-Group/.claude` repo. Cloud coverage is achieved via the
`cloud-bootstrap.sh` SessionStart hook instead.

## How cloud coverage works

The `settings.json` template includes a `SessionStart` hook that invokes
`cloud-bootstrap.sh`. When the harness repo is committed to a cloud project:

1. `CLAUDE_PROJECT_DIR` is set by the cloud platform.
2. `cloud-bootstrap.sh` fires on session start and symlinks harness artifacts into
   `$HOME/.claude`.
3. The plugin loads from the symlinked path.

If `CLAUDE_PROJECT_DIR` is unset (Desktop, or cloud without repo), the hook is a no-op.
