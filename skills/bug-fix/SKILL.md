---
name: "Bug Fix"
description: "Root cause analysis workflow with incremental TDD for bug fixes. Covers reproduce, analyze, regression test, fix, verify, and prevent. Use when fixing bugs to ensure proper methodology."
context: fork
agent: software-engineer
argument-hint: "Bug description and reproduction steps"
---

# Bug Fix Workflow

Follow root cause analysis methodology with incremental TDD.

## Process

1. **Reproduce**: Write a single failing test that demonstrates the bug
2. **Root Cause Analysis**: Trace the issue to the exact source
3. **Regression Test**: Ensure the failing test covers the exact bug scenario
4. **Fix**: Write minimum code to make the test pass
5. **Verify**: All tests pass including new regression test
6. **Prevention**: Apply design patterns to prevent recurrence
7. **PR**: Create PR with bug description, root cause, and fix

## Context

Gather state before starting:

```bash
# Recent failures and changes
git status
git log --oneline -5
```

## Worktree Isolation

Spawn the fixing engineer with `isolation: "worktree"`:

```
Agent({
  subagent_type: "software-engineer",
  isolation: "worktree",
  prompt: "Fix bug: [description]. Root cause: [analysis]..."
})
```

This ensures the fix is isolated and can be discarded if the approach is wrong.

## Root Cause Analysis Template

- **Symptom**: What the user sees
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Root Cause**: Why it happens (trace to exact file:line)
- **Fix**: What changes resolve it
- **Prevention**: How to prevent recurrence (pattern, validation, test)

## Fix Verification Checklist

- [ ] Failing test written BEFORE fix
- [ ] Fix is minimal - only what's needed
- [ ] All existing tests still pass
- [ ] No regressions introduced
- [ ] Root cause documented in PR description
- [ ] Design pattern applied if recurrence risk exists

## Design Patterns for Prevention

- **Guard clauses**: Prevent invalid state from propagating
- **Value Objects**: Ensure data integrity at construction
- **Strategy**: Replace fragile conditionals with polymorphism
- **Observer**: Decouple event handling to prevent cascading failures

## Tech-Stack-Specific Debugging

Read the project's tech stack pattern file for language-specific and framework-specific debugging guidance:
- Check `~/.claude/skills/[stack]-patterns/SKILL.md` (e.g., `react-native-patterns/SKILL.md`)
- The pattern file contains debugging strategies, common pitfalls, and framework-specific tools
- If no pattern file exists, apply general debugging principles: trace the call stack, check error boundaries, verify state management

## Prerequisite

- Bug reported with reproduction steps (or steps to be discovered)
- Codebase accessible and tests runnable

## Verdict

After the fix verification checklist passes, produce:
- **BUG_FIXED**: Regression test written, fix minimal, all tests green, root cause documented.
- **BUG_UNRESOLVED**: Cannot reproduce, or fix introduces regressions. Document findings.

## Phase Output

```
Verdict: BUG_FIXED / BUG_UNRESOLVED
Next: /code-review + /security-review (parallel, single message)
Artifacts: [list of changed/created files, regression test file]
Root cause: [1-2 sentence summary]
Agent summaries: [engineer's 2-3 sentence contribution summary]
```
