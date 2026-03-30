---
name: "Debug"
description: "Persistent debug state management for complex, multi-session bugs. Creates and maintains structured debug state files in pipeline-state/ that survive context compaction. Use when a bug requires multiple fix-test cycles, environment-dependent debugging, or spans sessions."
argument-hint: "Task ID or bug description"
---

# Debug

## What This Skill Does

Creates and maintains persistent debug state for complex bugs that require multiple fix-test cycles, environment-dependent debugging, or span multiple sessions. The state file survives context compaction and session boundaries.

## When to Invoke

- Bug requires environment-dependent testing (device, staging, browser)
- Root cause is not obvious after initial analysis
- Multiple hypotheses need systematic elimination
- Fix requires more than 2 fix-test cycles
- `/bug-fix` escalates to this skill for complex bugs

## Process

### Step 1: Create or Load Debug State

Check for existing debug state:
```bash
ls ~/.claude/pipeline-state/*-debug.md 2>/dev/null
```

If a debug state file exists for this task, load it and continue from the current state.

If no state exists, create `pipeline-state/{task-id}-debug.md`:

```markdown
---
task_id: {task-id}
phase: debugging
status: active
created: {ISO 8601}
updated: {ISO 8601}
---

## Debug: {bug description}

### Symptom
{What the user sees}

### Expected Behavior
{What should happen}

### Actual Behavior
{What actually happens}

### Reproduction Steps
1. {step 1}
2. {step 2}

### Hypothesis Log
| ID | Hypothesis | Confidence | Status | Evidence |
|----|-----------|------------|--------|----------|
| H1 | {hypothesis} | {0-100} | testing | {notes} |

### Elimination Log
| Timestamp | Hypothesis | Action Taken | Result |
|-----------|-----------|-------------|--------|
| {ISO 8601} | H1 | {what was tried} | {outcome} |

### Fix Attempts
| # | Description | Result | Commit |
|---|------------|--------|--------|
| 1 | {what was changed} | {pass/fail + details} | {SHA} |

### Environment Evidence
- {screenshot path, log excerpt, DOM dump, etc.}
```

### Step 2: Work the Hypotheses

For each debugging cycle:
1. Review the hypothesis log — which hypothesis has the highest confidence?
2. Design a test for the top hypothesis
3. Spawn an engineer (worktree) to implement the test/fix
4. Record the result in the elimination log
5. Update hypothesis confidence based on evidence
6. If eliminated: mark status `eliminated`, move to next hypothesis
7. If confirmed: mark status `confirmed`, proceed to fix

### Step 3: Update State After Each Cycle

After every fix attempt or hypothesis test:
1. Update the debug state file with results
2. Update the `updated` timestamp in frontmatter
3. Add elimination log entry
4. Adjust hypothesis confidences based on new evidence

### Step 4: Resolution

When the bug is fixed:
1. Update `status: resolved` in frontmatter
2. Record the confirmed hypothesis and final fix commit
3. Add a `### Resolution` section:
   ```markdown
   ### Resolution
   - **Root Cause**: {confirmed hypothesis}
   - **Fix**: {description of the fix}
   - **Commit**: {SHA}
   - **Verified**: {how verification was done}
   - **Prevention**: {what prevents recurrence}
   ```
4. The debug state file is cleaned up with other pipeline-state files after pipeline completion

## Constraints

- Maximum 5 fix-test iterations before escalating to user
- Each fix still goes through an agent (orchestrator never edits source)
- Pipeline gates (review, verify, test, accept) are SUSPENDED during the debug loop — they run once on the final working state
- Debug state file is the single source of truth — do not duplicate to memory

## Phase Output

```
Verdict: DEBUG_ACTIVE / DEBUG_RESOLVED / DEBUG_ESCALATED
Next: If RESOLVED → resume pipeline from Review phase
      If ESCALATED → user decides next steps
      If ACTIVE → continue debugging loop
State: pipeline-state/{task-id}-debug.md
```
