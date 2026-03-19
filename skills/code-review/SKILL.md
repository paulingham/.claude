---
name: "Code Review"
description: "Review phase skill: spawn code-reviewer agent to audit code for SOLID/DRY violations, security issues, test quality, performance, and complexity. Produces APPROVE or CHANGES_REQUESTED verdict."
parallel_group: "review"
context: fork
agent: code-reviewer
---

# Code Review

## What This Skill Does

Automates the Review phase code audit. Spawns a read-only code-reviewer agent to assess code quality against engineering standards.

## Current Context
- Branch: !`git branch --show-current`
- Changed files: !`git diff main...HEAD --name-only 2>/dev/null || echo 'N/A'`
- Diff stats: !`git diff main...HEAD --stat 2>/dev/null || echo 'N/A'`

## When to Invoke

- After Build phase completes (tests green, shape constraints met)
- Run IN PARALLEL with `/security-review` — both are read-only, independent
- Both must APPROVE before advancing to Verify phase

## Process

### 1. Gather Context

```bash
git diff main...HEAD --stat
git log main...HEAD --oneline
```

### 2. Spawn Code Reviewer

```
Agent({
  subagent_type: "code-reviewer",
  prompt: "Review the changes on this branch against main. Check for:
    - SOLID/DRY violations
    - Test quality (coverage, meaningful assertions, edge cases)
    - Performance red flags (N+1 queries, unnecessary re-renders, memory leaks)
    - Complexity (CC > 5, nesting > 2, methods > 5 lines, files > 50 lines)
    - Naming clarity and code readability
    Produce a verdict: APPROVE or CHANGES_REQUESTED with specific findings."
})
```

No `isolation: "worktree"` — code-reviewer is read-only.

### 3. Process Verdict

- **APPROVE**: Advance to next phase. Record reviewer summary for PR narrative.
- **CHANGES_REQUESTED**: Spawn the original engineer (with worktree) to address findings. Then re-run this skill.

## Review Checklist

- [ ] Shape constraints met (see `rules/engineering-protocol.md`)
- [ ] No DRY violations (duplicated logic)
- [ ] SRP: each class/module has one reason to change
- [ ] Tests are meaningful (not just coverage padding)
- [ ] No TODO/FIXME without linked ticket
- [ ] Error handling follows guard clause pattern
- [ ] No hardcoded values (extract to constants)

## Parallel Execution

This skill belongs to the `review` parallel group. It is dispatched via Parallel Dispatch Protocol (see `rules/parallel-dispatch-protocol.md`), not via sequential Skill tool invocation. The code-reviewer agent reads this file directly and executes it.

When dispatched in parallel:
1. The orchestrator spawns code-reviewer + security-engineer in a single message
2. Each agent reads its own skill file independently
3. The orchestrator collects both verdicts before proceeding

## Prerequisite

- Build phase complete: BUILD_COMPLETE verdict from `/build-implementation`, `/refactor`, or `/bug-fix`
- Must be dispatched IN PARALLEL with `/security-review` via Parallel Dispatch Protocol

## Phase Output

```
Verdict: APPROVE / CHANGES_REQUESTED
Next: If BOTH code-review and security-review APPROVE → /verify
      If CHANGES_REQUESTED → spawn engineer to fix → re-invoke BOTH review skills
Findings: [list of specific findings with severity]
Agent summaries: [code-reviewer's 2-3 sentence summary]
```
