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

## Release process (SHA-based versioning)

`harness@adviser-group` uses **SHA-based versioning**. There is no `version` field in
`.claude-plugin/plugin.json`. The plugin version is the git commit SHA of the local
marketplace clone. No manual version bump in `plugin.json` is needed or permitted.

**To release a new harness version:**

1. Merge your changes to `main` in `Adviser-Group/.claude`.
2. Re-paste `managed-settings.json` into the Anthropic enterprise console → Managed Settings.
3. Engineers' next session start automatically `git pull`s the new SHA and runs
   `claude plugin update` to sync the cache.

**Rollback:** revert the commit on `main`; the next engineer session start syncs to the
revert SHA automatically.

**If you ever need to pin a specific version:** re-introduce `"version": "<sha>"` in
`.claude-plugin/plugin.json`. Remove the pin when it is no longer needed.

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

The cloud-bootstrap hook is a no-op on Desktop/local sessions: it only runs when
BOTH `CLAUDE_CODE_REMOTE=true` AND `CLAUDE_PROJECT_DIR` are set. If either is
unset (Desktop, local CLI, or cloud runner without the harness repo committed), the
hook exits immediately without doing anything.

## settings.json design notes

- **`enabledPlugins`** uses list form `["harness@adviser-group"]` — the canonical
  format for repo-committed `settings.json` (as opposed to `managed-settings.json`
  which uses dict form `{"harness@adviser-group": true}` for enterprise console).
- **`extraKnownMarketplaces` is intentionally absent**: Claude Code's bundled git
  fails on private dot-named repos (`Adviser-Group/.claude`). Cloud coverage is
  provided by the `cloud-bootstrap.sh` SessionStart hook instead.
- **Cloud-runner coverage**: When the harness repo is committed to a cloud project,
  `cloud-bootstrap.sh` symlinks harness artifacts into `$HOME/.claude` so the plugin
  loads. This is a no-op on Desktop/local sessions where `CLAUDE_CODE_REMOTE` is
  unset or `CLAUDE_PROJECT_DIR` is unset.

## Required PAT scopes for ORG_SYNC_TOKEN

Configure `ORG_SYNC_TOKEN` as an org-level secret with the following minimum scopes:

| Workflow | Required scopes |
|----------|----------------|
| `repository-created.yml` | `repo` (write to new repos) + `pull-requests:write` |
| `required-workflow-drift-check.yml` | `repo` (read across org) + `issues:write` (drift issue creation) |
| `repo-file-sync.yml` | `repo` (write to target repos) |

Use the narrowest scopes your branch protection rules allow.

## repo-file-sync.yml — stub requiring configuration

The `repo-file-sync.yml` workflow is a **stub**. The sync step (step 2) contains a
placeholder `echo` command and does not sync anything until you configure a sync
mechanism. Before running it:

1. Choose a sync action (e.g. `BetaHuhn/repo-file-sync-action`) or write a custom
   script.
2. Configure `.github/sync.yml` with the file → repo mapping.
3. **SHA-pin any third-party sync action** you add to the stub before promoting —
   this workflow becomes an org-required workflow and must meet the same supply-chain
   bar as the other two.

## Direct-push-to-main in repository-created.yml

`repository-created.yml` pushes directly to the main branch of newly created repos.
This is intentional: brand-new repos have no branch protection rules yet. The
security of this path rests entirely on the integrity of the `Adviser-Group/org-defaults`
repository. If your org policy requires PRs for all pushes, modify the workflow to
open a PR instead of pushing directly.
