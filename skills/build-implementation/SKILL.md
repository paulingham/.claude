---
name: "build-implementation"
description: "Use when user wants to Structured build phase: read per-AC failing-test stubs from the architect, implement via the ATDD protocol (batched RED, implement, refactor, mutation gate), enforce shape constraints. Use at the start of any Build phase."
context: fork
agent: software-engineer
argument-hint: "Acceptance criteria or story to implement"
---

# Build Implementation

## What This Skill Does

Prescribes the exact procedure for the Build phase of the delivery pipeline. Engineers consume the architect's per-AC failing-test stub list, implement each slice via the ATDD cycle (three test invocations per slice plus a mutation gate), and enforce shape constraints continuously.

## Dispatch Mode

This skill is dispatched via the Agent tool with `isolation: "worktree"`. The orchestrator NEVER invokes this skill via the Skill tool directly. The agent reads this file and executes it in an isolated worktree.

## Procedure

### Step 1: Read AC Test Stubs from the Plan

Before writing any code:
1. Open `pipeline-state/{task-id}-plan.md` and locate the **Failing Test Stubs (per AC)** section the architect produced.
2. For each AC in this slice, the stub list names: test file path, test name, assertion intent.
3. **If any AC has no stub, halt immediately** — surface the gap to the architect and request a stub. Implementation cannot begin without a complete stub list.
4. The stub list IS your implementation plan. Three test invocations per slice — not three per AC, three per slice. See `rules/engineering-protocol.md` § ATDD Protocol for the full cycle.

### Step 1b: Install Required Dependencies

If the implementation requires new packages not yet in `package.json`:
1. Install the package: `npm install <package>` (or equivalent)
2. Verify the installation: `npm ls <package>` (or equivalent)
3. Commit `package.json` and lock file separately: "chore: add <package> for <reason>"
4. Proceed with the batched-RED step — the first failing batch validates the dependency works.

If the orchestrator's prompt specifies dependencies, install them here. If you discover a needed dependency during implementation, install it at that point.

### Step 2: Implement Slice via ATDD (Three test invocations per slice)

Follow the ATDD Protocol in `rules/engineering-protocol.md`:

1. **BATCHED RED**: Write every AC test as one batch (the architect's stubs verbatim). Run the suite ONCE. Capture the RED output. Verify each test fails for the right reason — the named behavior is absent.
2. **IMPLEMENT FREELY**: Write production code until every batched test passes. Shape constraints apply continuously: 8-line method cap, CC <= 5, nesting <= 2, 50-line file cap. Fix as you go, not at the end. Run the suite ONCE. Capture the GREEN output.
3. **REFACTOR WHILE GREEN**: Tighten names, extract duplication (DRY on 2nd occurrence), confirm shape on every touched file. Run the suite ONCE more. Capture the post-refactor GREEN output.
4. **MUTATION GATE**: Run mutation testing on changed lines (Stryker / Mutant / mutmut, or the manual fallback in `skills/verify/SKILL.md`). Score >= 70% required. If <70%, add tests targeting the surviving mutations and return to step 2 — the slice is NOT complete.
5. **COMMIT** with the four audit artifacts: batched RED output, post-implementation GREEN output, post-refactor GREEN output, mutation report.

**Exception cycles** — bug fixes, complex algorithmic logic, and security-sensitive code retain per-behaviour RED-GREEN-REFACTOR. See `rules/engineering-protocol.md` § When per-behaviour TDD Still Applies (Exceptions). For those cases follow `skills/bug-fix/SKILL.md` instead of the batched cycle.

### Step 3: Shape Check After Every File

After completing or modifying ANY file, verify all metrics in `rules/engineering-protocol.md` (8-line functions, 50-line files, CC <= 5, nesting <= 2, DRY).

If any metric is violated, refactor BEFORE moving to the next test case.

### Step 3b: Optional Tool Synthesis Escalation

If the standard toolset (Read, Grep, Glob, Bash one-liners, project-shipped scripts) is insufficient and a one-shot scratch tool would unblock progress, invoke `/tool-synthesis`. Triggers (any one):

- The same lookup/transformation has been performed manually **3+ times** in this task
- No extant tool covers the operation cleanly (no `rg` pattern, no `ast-grep` rule, no project script)
- A repo-specific concern (custom DSL, generated file, codebase convention) makes off-the-shelf tools wrong

The synthesised tool lives in `${WORKTREE}/.claude-scratch-tools/`, is invoked via Bash, and is cleaned up before BUILD_COMPLETE. It NEVER reaches `main`. See `skills/tool-synthesis/SKILL.md` for the full procedure.

If a built-in tool covers it, USE IT — do not synthesise.

### Step 4: Self-Review Checklist Before Done

Before declaring the build complete:
- [ ] Every AC has at least one passing test
- [ ] Every function body ≤ 8 lines (counted, not estimated)
- [ ] Every file ≤ 50 lines (counted, not estimated)
- [ ] No nesting > 2 levels
- [ ] No DRY violations (no logic duplicated 2+ times)
- [ ] All tests pass
- [ ] ATDD audit trail visible (batched RED + post-implementation GREEN + post-refactor GREEN + mutation report >= 70%)
- [ ] If changes touch URL/auth/nav/WebView files: note that E2E will be required in Verify phase (see `rules/e2e-protocol.md` trigger matrix)
- [ ] If `/tool-synthesis` was invoked: `register.sh --cleanup ${WORKTREE}` ran AND `git status` shows no `.claude-scratch-tools/` entries

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

- Skipping the mutation gate → BLOCKED (a green suite is not the deliverable; the mutation report is)
- Implementing before the batched-RED output is captured → BLOCKED (RED is the audit artifact)
- Starting work when one or more ACs has no architect-produced test stub → BLOCKED (halt, surface to architect)
- Deferring shape violations to "clean up later" → BLOCKED
- Skipping the self-review checklist → BLOCKED

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

### Decision Record (Mandatory)

Include a `## Decision Record` section in the pipeline state file. This travels to the reviewer so they understand *why* before reading *what*:

```markdown
## Decision Record
- **Chose**: [approach taken]
  **Over**: [alternative considered]
  **Because**: [reasoning tied to ACs, project conventions, or engineering principles]
  **Watch**: [conditions under which this choice should be revisited]
```

Every non-trivial design choice gets an entry. Trivial choices (naming, formatting) do not. The reviewer uses this to focus their review on areas of genuine uncertainty rather than re-deriving intent from the diff.

### Context for Next Phase

Include a `## Context for Review` section in the pipeline state file:

```markdown
## Context for Review
- **Uncertainty flags**: [areas where the build agent is unsure — "I chose X but Y might be better"]
- **TDD audit summary**: [N tests added, key behaviors covered, any gaps noted]
- **Learned patterns applied**: [instincts from learning/instincts/ that influenced decisions]
- **Areas needing focus**: [specific files or patterns the reviewer should scrutinize]
```

This gives reviewers a guided entry point instead of a cold diff read.
$ARGUMENTS
</reason></package>