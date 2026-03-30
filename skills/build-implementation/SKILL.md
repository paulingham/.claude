---
name: "Build Implementation"
description: "Structured build phase: decompose ACs into test cases, implement via incremental TDD protocol, enforce shape constraints. Use at the start of any Build phase."
context: fork
agent: software-engineer
argument-hint: "Acceptance criteria or story to implement"
---

# Build Implementation

## What This Skill Does

Prescribes the exact procedure for the Build phase of the delivery pipeline. Ensures engineers implement one acceptance criterion at a time using incremental TDD, with shape checks after every file.

## Dispatch Mode

This skill is dispatched via the Agent tool with `isolation: "worktree"`. The orchestrator NEVER invokes this skill via the Skill tool directly. The agent reads this file and executes it in an isolated worktree.

## Procedure

### Step 1: Decompose ACs into Ordered Test Cases

Before writing any code:
1. List every acceptance criterion.
2. For each AC, identify the individual behaviors to test (happy path, error path, edge cases).
3. **Each test case should be a micro-task: ~1 TDD cycle (2-5 minutes of work).** If a test case feels larger, decompose further.
4. Order them by dependency: foundational behaviors first, composed behaviors last.
5. This ordered list IS your implementation plan. Each item = one RED-GREEN-REFACTOR cycle.

### Step 1b: Install Required Dependencies

If the implementation requires new packages not yet in `package.json`:
1. Install the package: `npm install <package>` (or equivalent)
2. Verify the installation: `npm ls <package>` (or equivalent)
3. Commit `package.json` and lock file separately: "chore: add <package> for <reason>"
4. Proceed with TDD — the first failing test validates the dependency works

If the orchestrator's prompt specifies dependencies, install them here. If you discover a needed dependency during TDD, install it at that point.

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

## Self-Review Gate (Mandatory Before Completion)

Before producing the Phase Output, the build agent MUST self-review:

1. **Type safety**: Run `tsc --noEmit` — zero errors
2. **Tests green**: Run full test suite — all passing
3. **Re-read all changed files** and check:
   - Function names reveal intent
   - No duplication across files (extract on 2nd occurrence)
   - Single responsibility per function/file
   - No unused imports, dead code, or commented-out blocks
   - Guard clauses over nested conditionals
4. **Fix everything found** — do not leave mechanical issues for the reviewer
5. **Shape compliance**: Hooks enforce this automatically. If a hook blocks your write, fix immediately.

The goal: the code-reviewer should find ZERO mechanical issues. Only design-level feedback should survive to review.

## Built-In Verification (Budget 5-8)

For small tasks (Complexity Budget 5-8), the build agent performs its own verification before completing:

1. **Contract tests**: Verify all new functions have tests that assert their contracts (inputs → outputs)
2. **Mutation spot-check**: For each function with conditional logic, mentally check: "If I swapped the branches, would a test catch it?" If not, add the test.
3. **Integration check**: If the change wires into an existing component, verify the integration test covers it.

This reduces the need for separate Verify and QA phases on small tasks. For Budget 9+ tasks, separate Verify and QA phases still apply.

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
