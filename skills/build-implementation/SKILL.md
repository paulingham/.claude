---
name: "Build Implementation"
description: "Structured build phase: decompose ACs into test cases, implement via incremental TDD protocol, enforce shape constraints. Use at the start of any Build phase."
---

# Build Implementation

## What This Skill Does

Prescribes the exact procedure for the Build phase of the delivery pipeline. Ensures engineers implement one acceptance criterion at a time using incremental TDD, with shape checks after every file.

## Procedure

### Step 1: Decompose ACs into Ordered Test Cases

Before writing any code:
1. List every acceptance criterion.
2. For each AC, identify the individual behaviors to test (happy path, error path, edge cases).
3. Order them by dependency: foundational behaviors first, composed behaviors last.
4. This ordered list IS your implementation plan.

### Step 2: Implement One Test Case at a Time

For each test case in order, follow the Incremental TDD Protocol in `rules/engineering-protocol.md`:
1. **RED**: Write ONE failing test. Run it. Verify RED for the right reason.
2. **GREEN**: Write MINIMUM code to pass. Run ALL tests. Verify GREEN.
3. **REFACTOR**: Shape check every touched file (see constraints below). Fix violations NOW. Run tests. Confirm GREEN.
4. Move to next test case.

### Step 3: Shape Check After Every File

After completing or modifying ANY file, verify all metrics in `rules/engineering-protocol.md` (5-line functions, 50-line files, CC <= 5, nesting <= 2, DRY).

If any metric is violated, refactor BEFORE moving to the next test case.

### Step 4: Self-Review Checklist Before Done

Before declaring the build complete:
- [ ] Every AC has at least one passing test
- [ ] Every function body ≤ 5 lines (counted, not estimated)
- [ ] Every file ≤ 50 lines (counted, not estimated)
- [ ] No nesting > 2 levels
- [ ] No DRY violations (no logic duplicated 2+ times)
- [ ] All tests pass
- [ ] TDD audit trail visible (RED/GREEN/REFACTOR output for each cycle)
- [ ] If changes touch URL/auth/nav/WebView files: note that E2E will be required in Verify phase (see `rules/e2e-protocol.md` trigger matrix)

## Worktree Isolation

All engineers spawned during Build MUST use `isolation: "worktree"`:

```
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "Implement [AC] following incremental TDD...
    Also read the project's tech stack pattern file if one exists
    at ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance."
})
```

**Parallel worktrees for independent slices:**
- If multiple ACs are independent (no shared files), spawn separate engineers in parallel worktrees
- Each worktree gets its own isolated copy of the repo
- Use a single message with multiple Agent calls to maximize parallelism
- If ACs share files, implement sequentially — merge first worktree before starting next

## Anti-Patterns

- Writing all tests first, then all implementation → BLOCKED
- Deferring shape violations to "clean up later" → BLOCKED
- Skipping the self-review checklist → BLOCKED
- Implementing without running tests between changes → BLOCKED

## Prerequisite

- Plan phase complete: story/AC defined (from `/epic-breakdown` or `/story-writing`)
- OR: refactoring target identified (use `/refactor` instead)
- OR: bug reproduction steps known (use `/bug-fix` instead)

## Verdict

After the self-review checklist passes, produce:
- **BUILD_COMPLETE**: All ACs have passing tests, all shape constraints met, TDD audit trail visible.
- **BUILD_FAILED**: Checklist items remain unresolved. List which items failed.

## Phase Output

```
Verdict: BUILD_COMPLETE / BUILD_FAILED
Next: /code-review + /security-review (parallel, single message)
Artifacts: [list of changed/created files]
Agent summaries: [each engineer's 2-3 sentence contribution summary]
```
