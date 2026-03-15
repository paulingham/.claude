---
name: "PR Creation Workflow"
description: "GitHub pull request workflow with validation, feature branch management, and automated PR creation. Use when completing features to create production-ready pull requests."
---

# PR Creation Workflow

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

## Context

Gather state before starting:

```bash
# Current branch and changes
git status
git log --oneline -5
git diff --stat
```

## Quick Start

```bash
# Complete PR workflow
git push -u origin feature/my-feature && \
gh pr create --title "..." --body "..."
```

## Step-by-Step Workflow

### 1. Verify Feature Branch

```bash
# Check current branch
git status

# If on main/master, create feature branch first
git checkout -b feature/add-notification-system
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
git add .

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

```bash
# Create PR with detailed description
gh pr create \
  --title "type(scope): description (TICKET-123)" \
  --body "$(cat <<'EOF'
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
EOF
)"
```

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
5. Create GitHub PR via `gh pr create`
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

## Best Practices

- Always run validation before pushing
- Use descriptive feature branch names
- Write comprehensive PR descriptions
- Include test results and coverage
- Reference tickets
- Add co-authoring attribution
- Never push to main/master
