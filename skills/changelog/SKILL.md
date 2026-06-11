---
name: "changelog"
description: "Use when user wants to ship a PR with a human-readable narrative and a changelog entry: derives a 'what changed and why' PR body plus a Keep-a-Changelog entry from the diff and the acceptance criteria. Called from /harness:pr-creation's Ship phase (advisory). Produces CHANGELOG_WRITTEN."
context: fork
agent: software-engineer
model: haiku
argument-hint: "Optional: path to CHANGELOG.md (defaults to repo-root CHANGELOG.md)"
---

# Changelog & PR Narrative

## What This Skill Does

Closes the technical-writing gap flagged in the harness audit: a production-grade
PR is not just a green diff, it ships a record a human can read. This skill takes
the `origin/main...HEAD` diff plus the acceptance criteria and produces two artifacts:

1. **PR narrative** — a "what changed and why" summary written for a reviewer who
   did not watch the build, suitable for the `## Summary` block of the PR body.
2. **Changelog entry** — a [Keep a Changelog](https://keepachangelog.com) entry
   (`Added` / `Changed` / `Fixed` / `Removed`) appended under the `Unreleased`
   heading of the project `CHANGELOG.md`.

It is invoked by `/harness:pr-creation` after the Final Gate emits APPROVED, so
every merged PR carries a narrative and a changelog line instead of relying on the
model to remember.

## When to Invoke

- During the Ship phase, before `pr-creation` assembles the PR body.
- Standalone, when the user asks for "a changelog entry" or "release notes" for
  the current branch's changes.

## Inputs (gather first)

```bash
WORKTREE="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
# Use origin/main as the base — a local `main` ref may be absent or stale inside
# a worktree, so `origin/main...HEAD` is the robust diff base (review finding GP-P3-1#3).
git -C "$WORKTREE" diff origin/main...HEAD --stat
git -C "$WORKTREE" log origin/main..HEAD --format='%s'   # commit subjects = change intents
```

Acceptance criteria come from the pipeline state (`$state_dir/{task-id}/intake.md`
or the story ACs); in standalone mode, infer them from the commit subjects.

## Procedure

### Step 1 — Classify the change

Map the diff + commit subjects to exactly one Keep-a-Changelog bucket per logical
change: `Added` (new capability), `Changed` (behaviour of existing capability),
`Fixed` (bug), `Removed` (deleted capability), `Security` (vuln fix). One line per
bucket, imperative voice, no trailing period — e.g. `Added changelog skill wired
into pr-creation (GP-P3-1)`.

### Step 2 — Write the PR narrative

Two to four sentences answering, in order: **what** changed (the observable
behaviour), **why** (the AC or problem it closes), and **how it was verified**
(the test that proves it). Lead with the outcome. No internal jargon a reviewer
outside the build would have to decode.

### Step 3 — Append the changelog entry

```bash
CHANGELOG="${1:-$WORKTREE/CHANGELOG.md}"
# Create the file with a Keep-a-Changelog skeleton if absent.
if [ ! -f "$CHANGELOG" ]; then
  printf '# Changelog\n\nAll notable changes to this project are documented here.\n\nThe format is based on [Keep a Changelog](https://keepachangelog.com).\n\n## [Unreleased]\n' > "$CHANGELOG"
fi
```

Insert each Step-1 line under the matching sub-heading of the `## [Unreleased]`
section (create the `### Added` / `### Changed` / … sub-heading if missing). Use the
**Edit tool** for this insertion — never an improvised shell `sed`/`awk`, which is an
unquoted-pattern footgun on changelog text. Never rewrite existing entries — append
only. Stage the file by name (never `git add .`).

## Verdict

- **CHANGELOG_WRITTEN**: PR narrative returned and `CHANGELOG.md` updated under
  `Unreleased`. Hand the narrative back to `pr-creation` for the `## Summary` block.
- **CHANGELOG_SKIPPED**: no functional change in the diff (docs/test-only) — return
  the narrative for the PR body but make no changelog edit, and say so.

## Phase Output

```
Verdict: CHANGELOG_WRITTEN / CHANGELOG_SKIPPED
PR narrative: [2-4 sentence what/why/verified summary]
Changelog entry: [the appended Unreleased line(s)]
```
