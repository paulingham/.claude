---
name: "pr-creation"
description: "Use when user wants to ship a feature: GitHub pull request workflow with validation, feature branch management, and automated PR creation. Runs the Ship phase after the Final Gate has emitted APPROVED. Produces PR_CREATED or PR_BLOCKED."
context: fork
agent: software-engineer
argument-hint: "Optional: PR title or 'auto' to derive from commit messages"
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

## Known Misfire Mode

**Symptom**: On the first Ship-phase dispatch the skill returns "standing by" (or an equivalent ack-only response) instead of executing Steps 0-5 below. No branch is created. No PR is opened. The pipeline stalls at the Ship gate with no verdict.

**Suspected root cause (not yet proven)**: the model-invocation routing layer scans the skill `description` field for action cues. Skills that auto-invoke reliably (e.g. `/harness:internal-eval`, `/harness:build-implementation`, `/harness:code-review`, `/harness:security-review`, `/harness:verify`, `/harness:product-acceptance`, `/harness:patch-critique`, `/harness:learn`) all start their description with the literal phrase `"Use when user wants to ..."`. Before this fix the pr-creation description started with `"GitHub pull request workflow ..."` — no `"Use when ..."` cue, no `argument-hint`, no `## Process` anchor. Without those, the skill body may have been loaded as reference documentation rather than an executable procedure.

**Workaround (when the misfire still recurs after the description fix)**:
1. Orchestrator dispatches a `fix-engineer` directly with a build-style spawn whose prompt is the literal contents of this SKILL.md's Steps 0-5.
2. Pass `Working directory: <worktree-path>` and the original task-id in the spawn prompt so the approval-token gate + worktree precondition both resolve.
3. Treat the fix-engineer's PR-URL return value as the `PR_CREATED` verdict for the Ship-phase state file. Manually write `$state_dir/{task-id}/ship.md` with `verdict: PR_CREATED` and the PR URL.

**Action note for operators investigating recurrences**:
- Compare this skill's frontmatter + body shape against `~/.claude/skills/internal-eval/SKILL.md` and `~/.claude/skills/learn/SKILL.md` — both auto-invoke reliably.
- Diff candidates to investigate: `description` prefix wording, presence of `## Process` heading with numbered `### Step N:` sub-headings, presence of `argument-hint`, presence of `disable-model-invocation` (only `deploy` sets this — confirms it's NOT load-bearing for normal dispatch).
- If you reproduce the misfire and prove the root cause, remove this section and tighten the regression guard in `tests/test_pr_creation_skill_frontmatter.py`.

## Prerequisites

- Feature branch created (`feature/description`)
- All changes ready to commit
- `gh` CLI installed and authenticated

## Step 0 — Approval Token Gate (HARD GATE)

Before any branch operations, verify that `/harness:product-acceptance` has authorized this PR:

```bash
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/approval-token.sh"
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
- **No active pipeline** (no `$state_dir/{task-id}/pipeline.md` and no legacy `$state_dir/{task-id}-pipeline.md`): manual PR path — gate skips, proceed.

Cross-references: `hooks/auto-pr.sh` performs an advisory read of the same token and suppresses its PR suggestion when the gate is closed.

## Verification Freshness Dependency

`hooks/quality-gate.sh` runs on `gh pr create` and includes the new `_qg_check_freshness` check (extension landed in this slice). The check reads `$state_dir/{task-id}/verification-evidence.json` written by `/harness:verify` Step 6 and FAILs (rc=1 → quality-gate exit 2) when the recorded `git_head` does not match the current worktree HEAD, the file is missing, or the verdict is not `VERIFIED` / `VERIFIED_WITH_SKIP`. Operators must re-run `/harness:verify` before re-attempting `gh pr create` in that case.

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

All subsequent commands in this skill use `git -C "$WORKTREE" ...` or `(cd "$WORKTREE" && ...)`. Bare `git checkout|switch|merge|...` and bare `gh pr create` are blocked by `hooks/main-branch-guard.sh` regardless of cwd. See `protocols/agent-protocol.md > ## Main-Branch Invariant`.

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

# Branch creation uses worktree add — the only sanctioned form
git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b feature/add-notification-system
# The orchestrator handles this via hooks/worktree-create.sh; agents reference $WORKTREE_PATH
```

### 2. Run Pre-Push Validation

#### Hook-Change Pytest Gate (HARD GATE)

Run the gate BEFORE calling any PR-creation command (step 5 below):

```bash
# $WORKTREE is already resolved and validated by the Worktree Precondition above.
bash "$WORKTREE/skills/pr-creation/lib/check-hook-pytest-gate.sh"
GATE_EXIT=$?
if [ "$GATE_EXIT" -ne 0 ]; then
  echo "PR_BLOCKED — hook-change pytest gate failed. See output above."
  exit 2
fi
```

This gate fires when `main...HEAD` touches a `hooks/*.sh` or `hooks/_lib/*.sh` body
line, and runs the targeted pytest subset from the worktree. Any red blocks the PR
(exit 2). It is bypass-proof vs `gh api` because it is a SKILL STEP — see GP-19.

- **No hook body change**: gate no-ops, exits 0, no pytest invoked.
- **Hook body changed + subset green**: exits 0, proceed.
- **Hook body changed + subset red**: exits 2 (`PR_BLOCKED`). Fix the failing tests, then retry Ship.
- **Bypass** (pre-existing, unrelated failures confirmed): `CLAUDE_DISABLE_HOOK_PYTEST_GATE=1` then re-run Ship.

#### Quality Gate (HARD GATE — path-independent)

Run AFTER the hook-pytest gate and BEFORE any PR-creation command (step 5 below).
This gate runs `_qg_check_tests|lint|audit|shape|contract|freshness` regardless of
which tool creates the PR (`gh pr create`, `gh api`, or MCP `create_pull_request`).
A Bash hook matcher fires only for `gh pr create` — this skill step is bypass-proof.

WHY: `hooks/quality-gate.sh:23` exits 0 for any non-`gh pr create` tool, so MCP and
`gh api` skip the hook entirely. This step closes that gap. GP-C1, issue #33106
(`permissionDecision:deny` is not enforced for MCP tools).

Cross-references: §Verification Freshness Dependency (evidence must be fresh before
this gate can pass).

```bash
# $WORKTREE is already resolved and validated by the Worktree Precondition above.
bash "$WORKTREE/skills/pr-creation/lib/check-quality-gate.sh"
GATE_EXIT=$?
if [ "$GATE_EXIT" -ne 0 ]; then
  echo "PR_BLOCKED — quality gate failed. See output above."
  exit 2
fi
```

- **All checks pass**: exits 0, proceed to commit + push + PR creation.
- **Any check fails**: exits 2 (`PR_BLOCKED`). Fix the failing check, then retry Ship.
- **Bypass** (pre-existing, unrelated failures confirmed): `CLAUDE_DISABLE_QUALITY_GATE=1` then re-run Ship.
- **Skip heavy checks only** (test-suite isolation): `CLAUDE_QG_SKIP_CHECKS=1` — freshness still evaluated.

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

Before calling `gh pr create` (or `gh api .../pulls`, or MCP `create_pull_request`),
run `check-quality-gate.sh` to gate ALL PR creation paths (see §Step 2 Quality Gate
above). `gh api .../pulls` bypasses the Bash hook — this step is the path-independent
gate. GP-C1, issue #33106.

```bash
bash "$WORKTREE/skills/pr-creation/lib/check-quality-gate.sh"
GATE_EXIT=$?
[ "$GATE_EXIT" -ne 0 ] && { echo "PR_BLOCKED — quality gate failed."; exit 2; }
```

Then append the eval-baseline stamp to the body:

```bash
# Capture the stamp (harness repo only; no-op in other projects)
STAMP=""
if [ -x "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/skills/internal-eval/score/stamp-pr-body.sh" ]; then
  STAMP="$(bash "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/skills/internal-eval/score/stamp-pr-body.sh" 2>/dev/null || true)"
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
4. **Run `check-quality-gate.sh` BEFORE creating the PR** (HARD GATE — path-independent):
   ```bash
   bash "$WORKTREE/skills/pr-creation/lib/check-quality-gate.sh"
   GATE_EXIT=$?
   [ "$GATE_EXIT" -ne 0 ] && { echo "PR_BLOCKED — quality gate failed."; exit 2; }
   ```
   WHY: `gh api .../pulls` bypasses the Bash hook at `hooks/quality-gate.sh:23`; this
   step gates ALL PR paths (gh pr create, gh api, MCP). GP-C1, issue #33106.
5. Push to remote with `-u` flag
6. Create GitHub PR via `(cd "$WORKTREE" && gh pr create ...)` — the `cd "$WORKTREE"` prefix is required by the main-branch invariant guard
7. Return PR URL to user

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

## Spec-Blind Validation

Every PR body includes a `## Spec-Blind Validation` section reflecting the spec-blind-validator's verdict from the Final Gate. The validator runs as a 5th Final Gate teammate that authors black-box behavioural tests from the AC plan + public API surface ONLY — never from `src/` internals.

The section's content depends on the verdict:

- **SPEC_BLIND_VALIDATED** — `spec-blind validator passed: independent test suite cross-validates the build-time tests.`
- **SPEC_BLIND_INSUFFICIENT_SURFACE** — `spec-blind validator was skipped — no public-surface artifacts found in this repo. See SKILL.md § Future Work for V2 harness-aware path.`
- **SPEC_BLIND_FAILED** — should not appear in a merged PR (gate must pass before Ship); included here for forensic traceability if the gate was suppressed.
- **SPEC_BLIND_BLOCKED** — should not appear in a merged PR (HALT pipeline routing per `protocols/verdict-catalog.md`); included here for operator visibility on suppressed-gate forensics.

The section makes the no-op visible — silent skips would let the gate become unattended on convention-poor projects (per the plan's AC18 mitigation).

## Decision Narrative

Every PR includes a non-technical decision narrative section:

1. **Collect agent summaries**: Include a summary request in the original agent spawn prompt: "Before finishing, output a '## Agent Summary' section with 2-3 sentences on what you did, decisions made, and trade-offs." The orchestrator collects these summaries from agent outputs after completion.
2. **Assemble into PR body** under a "## Decision Log" section:
   - **What**: What was built and why (business context)
   - **Why**: Key decisions and trade-offs (what was considered and rejected)
   - **How**: How each agent contributed (design rationale, review findings)
   - **Verified**: Verification report summary in plain language
3. Must be readable by non-technical stakeholders (product owners, designers)

## Changelog & PR Narrative

Before assembling the PR body (Step 5), invoke `/harness:changelog` to derive the
`## Summary` narrative and append a Keep-a-Changelog entry under `Unreleased`:

1. Run `/harness:changelog` against `main...HEAD` + the task ACs.
2. Use its returned PR narrative as the `## Summary` block of the PR body.
3. The skill stages the project `CHANGELOG.md` edit; commit it with the change so
   every merged PR carries a human-readable changelog line.
4. **CHANGELOG_SKIPPED** (docs/test-only diff) is non-blocking — use the returned
   narrative for the body and proceed without a changelog edit.

This closes the technical-writing gap: a production-grade PR ships a record a
non-author can read, not just a green diff. See `~/.claude/skills/changelog/SKILL.md`.

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

- Accept phase complete: `/harness:product-acceptance` returned APPROVED
- All prior phase verdicts: BUILD_COMPLETE, APPROVE (both reviews), VERIFIED, COVERED, APPROVED
- Approval token written by /harness:product-acceptance (verified at Step 0 above).

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
