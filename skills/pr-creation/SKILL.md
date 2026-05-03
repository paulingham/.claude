---
name: "pr-creation"
description: "GitHub pull request workflow with validation, feature branch management, and automated PR creation. Use when completing features to create production-ready pull requests."
context: fork
agent: software-engineer
---

# PR Creation Workflow

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## What This Skill Does

Automated pull request creation with validation:
1. Run pre-push validation (linting, tests, security)
2. Ensure on feature branch
3. Commit all changes with descriptive message
4. Push to remote
5. Create GitHub PR with proper formatting
6. Return PR URL

## Prerequisites

- Feature branch created (`feature/description`)
- All changes ready to commit
- `gh` CLI installed and authenticated

## Step 0 — Approval Token Gate (HARD GATE)

Before any branch operations, verify that `/product-acceptance` has authorized this PR:

```bash
source "$HOME/.claude/hooks/_lib/approval-token.sh"
bash "$(dirname "$0")/lib/check-approval-token.sh"
GATE_EXIT=$?
if [ "$GATE_EXIT" -ne 0 ]; then
  echo "PR_BLOCKED — see output above for remediation."
  exit 2
fi
```

Or invoke via the skill wrapper directly:
```bash
bash "$WORKTREE/skills/pr-creation/lib/check-approval-token.sh"
```

- **APPROVED** or **APPROVED_WITH_CONDITIONS**: proceed to Step 1.
- **Missing token** or **REJECTED**: exits with `PR_BLOCKED` message including remediation hint.
- **No active pipeline** (no `pipeline-state/{task-id}/pipeline.md` and no legacy `pipeline-state/{task-id}-pipeline.md`): manual PR path — gate skips, proceed.

Cross-references: `hooks/auto-pr.sh` performs an advisory read of the same token and suppresses its PR suggestion when the gate is closed.

## Worktree Precondition (HARD GATE)

This skill mutates HEAD-bearing state (creates branches, runs `gh pr create` which pushes the current branch). It MUST run inside a worktree, never against REPO_ROOT directly. Resolve the worktree path at skill entry:

```bash
WORKTREE="$(cd "$(git rev-parse --show-toplevel)" && pwd -P)"
COMMON_DIR_ABS="$(cd "$WORKTREE" && cd "$(git rev-parse --git-common-dir)" && pwd -P)"
GIT_DIR_ABS="$(cd "$WORKTREE" && cd "$(git rev-parse --git-dir)" && pwd -P)"
if [[ "$COMMON_DIR_ABS" == "$GIT_DIR_ABS" ]]; then
  echo "ERROR: pr-creation must run from a worktree; cwd resolves to REPO_ROOT" >&2
  exit 2
fi
```

All subsequent commands in this skill use `git -C "$WORKTREE" ...` or `(cd "$WORKTREE" && ...)`. Bare `git checkout|switch|merge|...` and bare `gh pr create` are blocked by `hooks/main-branch-guard.sh` regardless of cwd. See `rules/agent-protocol.md > ## Main-Branch Invariant`.

## Context

Gather state before starting:

```bash
# Current branch and changes
git -C "$WORKTREE" status
git -C "$WORKTREE" log --oneline -5
git -C "$WORKTREE" diff --stat
```

## Quick Start

```bash
# Complete PR workflow (must run from a worktree — see Worktree Precondition)
(cd "$WORKTREE" && git push -u origin feature/my-feature && \
 gh pr create --title "..." --body "...")
```

## Step-by-Step Workflow

### 1. Verify Feature Branch

```bash
# Check current branch
git -C "$WORKTREE" status

# If on main/master, create feature branch first (delegated form required)
git -C "$WORKTREE" checkout -b feature/add-notification-system
```

### 2. Run Pre-Push Validation

Run all quality checks before pushing:
- Linting (language-appropriate linter)
- Security scanning
- Test suite with coverage
- Database consistency checks (if applicable)

Only proceed when all checks pass.

### 3. Commit Changes

```bash
# Stage all changes
git add [specific files by name — never use 'git add .' or 'git add -A']
# Review staged files before committing: git diff --cached --name-only
# Verify no .env, credentials, or binary artifacts are included

# Commit with descriptive message
git commit -m "$(cat <<'EOF'
type(scope): description

- Detail 1
- Detail 2
- Detail 3

Closes TICKET-123

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 4. Push to Remote

```bash
# Push feature branch (first time)
git push -u origin feature/add-notification-system

# Or subsequent pushes
git push
```

### 5. Create Pull Request

Before calling `gh pr create`, append the eval-baseline stamp to the body:

```bash
# Capture the stamp (harness repo only; no-op in other projects)
STAMP=""
if [ -x "$HOME/.claude/skills/internal-eval/score/stamp-pr-body.sh" ]; then
  STAMP="$(bash "$HOME/.claude/skills/internal-eval/score/stamp-pr-body.sh" 2>/dev/null || true)"
fi

# Create PR with detailed description + eval baseline stamp.
# The (cd "$WORKTREE" && ...) wrapper is required by the main-branch invariant
# guard — bare `gh pr create` is blocked by hooks/main-branch-guard.sh.
(cd "$WORKTREE" && gh pr create \
  --title "type(scope): description (TICKET-123)" \
  --body "$(cat <<EOF
## Summary
[3-5 sentence overview of what changed and why]

**Changes:**
- [List of major changes with file types]

**Coverage:** [X%] (meets/exceeds threshold)

## Testing
- [Test category 1]
- [Test category 2]
- [Coverage details]

## Related
Closes [TICKET-XXX or issue number]

${STAMP}
EOF
)")
```

The eval-baseline stamp is appended to every PR body so reviewers see the latest suite pass rate + `harness_ref` SHA without per-PR reruns. See `~/.claude/skills/internal-eval/score/stamp-pr-body.sh`.

## Branch Naming Conventions

**Pattern**: `{type}/{description}`

Types:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation only
- `test/` - Test improvements

## Autonomous PR Creation

When user says "create PR", execute autonomously:

1. Run validation checks (MUST pass)
2. Verify feature branch or create
3. Stage and commit all changes
4. Push to remote with `-u` flag
5. Create GitHub PR via `(cd "$WORKTREE" && gh pr create ...)` — the `cd "$WORKTREE"` prefix is required by the main-branch invariant guard
6. Return PR URL to user

**Don't ask** -- just do it with reasonable defaults based on commit messages, files changed, and tests added.

## Error Handling

### Validation fails
Review output, fix failures, re-run until passing.

### Already on main branch
Create feature branch, move changes to it.

### PR creation fails (gh CLI)
Verify `gh auth status`, re-authenticate if needed, retry.

### Remote branch conflicts
Pull latest main, rebase feature branch, resolve conflicts, push with `--force-with-lease`.

## Decision Narrative

Every PR includes a non-technical decision narrative section:

1. **Collect agent summaries**: Include a summary request in the original agent spawn prompt: "Before finishing, output a '## Agent Summary' section with 2-3 sentences on what you did, decisions made, and trade-offs." The orchestrator collects these summaries from agent outputs after completion.
2. **Assemble into PR body** under a "## Decision Log" section:
   - **What**: What was built and why (business context)
   - **Why**: Key decisions and trade-offs (what was considered and rejected)
   - **How**: How each agent contributed (design rationale, review findings)
   - **Verified**: Verification report summary in plain language
3. Must be readable by non-technical stakeholders (product owners, designers)

## Multi-Repo PRs (When Manifest Exists)

When the pipeline provides a manifest path, this skill creates linked PRs:

### Procedure
1. **Read manifest**: Get repo list, dependency graph, GitHub config
2. **Create PRs in dependency order**: Providers first, consumers after
3. **Cross-reference**: Each PR body includes:
   ```markdown
   ## Related PRs
   - Depends on: {org}/{provider-repo}#{N} (must merge first)
   - Depended on by: {org}/{consumer-repo}#{N}
   ```
4. **Apply labels**: From manifest `## Services > GitHub > labels` if configured
5. **Return all PR URLs**: The orchestrator tracks them in the pipeline state PR Manifest

### Merge Order
The orchestrator handles merge ordering — this skill only creates PRs. It adds a `## Merge Order` note to each PR body so human reviewers understand the dependency.

## Best Practices

- Always run validation before pushing
- Use descriptive feature branch names
- Write comprehensive PR descriptions
- Include test results and coverage
- Include decision narrative from participating agents
- Reference tickets
- Add co-authoring attribution
- Never push to main/master

## Prerequisite

- Accept phase complete: `/product-acceptance` returned APPROVED
- All prior phase verdicts: BUILD_COMPLETE, APPROVE (both reviews), VERIFIED, COVERED, APPROVED
- Approval token written by /product-acceptance (verified at Step 0 above).

## Verdict

- **PR_CREATED**: PR URL returned, quality gate hook passed.
- **PR_BLOCKED**: Quality gate failed. Fix issues and retry.

## Phase Output

```
Verdict: PR_CREATED / PR_BLOCKED
Next: Pipeline complete. Report PR URL to user.
PR URL: [GitHub PR URL]
Agent summaries: [assembled decision narrative from all participating agents]
```
