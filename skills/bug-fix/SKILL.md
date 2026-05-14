---
name: "bug-fix"
description: "Root cause analysis workflow with incremental TDD for bug fixes. Covers reproduce, analyze, regression test, fix, verify, and prevent. Use when fixing bugs to ensure proper methodology."
context: fork
agent: software-engineer
argument-hint: "Bug description and reproduction steps"
---

# Bug Fix Workflow

Follow root cause analysis methodology with per-behaviour RED-GREEN-REFACTOR (the bug-fix exception to ATDD's batched cycle — see `protocols/atdd-procedure.md` § When per-behaviour TDD Still Applies).

> **IRON LAW: WRITE THE FAILING REPRO TEST AND SEE IT FAIL BEFORE WRITING ANY FIX CODE. NO EXCEPTIONS.**
>
> The repro test IS the contract. One bug, one repro test, observed RED for the right reason, BEFORE the fix is written. Bug fixes do NOT use the batched-RED ATDD cycle — per-behaviour RED-first TDD is mandatory here.

## Process

0. **Step 0 — AssertFlip Reproducer (MANDATORY, BEFORE anything else)**: Write a *passing* test against the buggy code that captures its current (wrong) behaviour, then **invert the assertions** so the test fails on the bug. This guarantees a failing-for-the-right-reason reproducer before any fix attempt. Capture the path to this test file as the **reproducer artifact** — it is a required payload field on `BUG_FIXED`. Technique: arXiv 2507.17542 (AssertFlip), 43.6% fail-to-pass on SWT-Bench-Verified. Do NOT skip this in favour of a free-hand failing test — AssertFlip eliminates the "test fails for the wrong reason" failure mode (missing import, wrong fixture, typo) that ordinary RED-first authoring is prone to.
1. **Reproduce (MANDATORY RED)**: Run the suite ONCE with the Step 0 test in place. Capture the RED output. Verify it fails for the actual bug — not a syntax error, not a missing import. The RED output + the reproducer test path together are the audit artifact that proves the bug existed; without both, you have not reproduced anything.
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

## Complex Bug Escalation

If the bug meets ANY of these criteria, invoke `/debug` to create persistent debug state:
- Requires environment-dependent testing (device, staging, browser)
- Root cause is not obvious after initial analysis
- Multiple hypotheses need systematic elimination
- Fix requires more than 2 fix-test cycles

The `/debug` skill creates `pipeline-state/{task-id}/debug.md` that survives context compaction and session boundaries. See the debug skill for the full hypothesis tracking protocol.

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
- **BUG_FIXED**: Regression test written, fix minimal, all tests green, root cause documented. Payload MUST include `reproducer_artifact: <path>` pointing at the Step 0 AssertFlip test that observed RED before the fix. Verdict without this field is rejected as incomplete.
- **BUG_UNRESOLVED**: Cannot reproduce, or fix introduces regressions. Document findings.

## Phase Output

```
Verdict: BUG_FIXED / BUG_UNRESOLVED
Next: /code-review + /security-review (parallel, single message)
Reproducer artifact: <path/to/test> (REQUIRED on BUG_FIXED — AssertFlip Step 0 output)
Artifacts: [list of changed/created files, regression test file]
Root cause: [1-2 sentence summary]
Agent summaries: [engineer's 2-3 sentence contribution summary]
```
$ARGUMENTS
