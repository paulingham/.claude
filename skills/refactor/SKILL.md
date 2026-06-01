---
name: "refactor"
description: "Use when user wants to Safe refactoring workflow: identify smell, write characterization tests, refactor in small steps, verify green after each. Use for refactoring code with confidence."
context: fork
agent: software-engineer
argument-hint: "Code smell and target files"
---

# Safe Refactoring Workflow

## What This Skill Does

Guides safe refactoring: never change behavior without tests, commit after each step.

## Worktree Isolation

Spawn the refactoring engineer with `isolation: "worktree"`:

```
Agent({
  subagent_type: "software-engineer",
  isolation: "worktree",
  prompt: "Refactor [target]: smell is [smell], characterization tests needed...
    Also read the project's tech stack pattern file if one exists
    at ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance."
})
```

If the refactoring is rejected, the worktree is discarded — no cleanup needed.

## Process

### 1. Identify the Smell

Common smells:
- Long method (> 8 lines)
- Large class (> 50 lines)
- Feature envy (method uses another object's data more than its own)
- Duplicated logic (3+ occurrences)
- Primitive obsession (raw types instead of value objects)
- Conditional complexity (nested ifs, case statements)

### 2. Write Characterization Tests

Before touching any code:
- Write tests that document current behavior exactly
- Cover happy path, edge cases, and error paths
- Run tests — they MUST pass before refactoring begins
- If tests already exist, verify they cover the code being changed

### 3. Refactor in Small Steps

One transformation at a time. Run tests after each step.

**Common patterns:**
- **Extract Method**: Pull logic into a named method
- **Extract Class**: Move related methods and data to a new class
- **Replace Conditional with Polymorphism**: Strategy or template method
- **Introduce Value Object**: Replace primitives with domain types
- **Move Method**: Relocate to the class that owns the data
- **Replace Magic Number/String**: Extract to named constant

### 4. Verify After Each Step

- Run full test suite — must be green
- Commit after each successful step
- If tests fail, revert the last step and try a smaller change

### 5. Final Check

- All tests green
- No behavior changes (characterization tests unchanged)
- Code meets engineering standards (8-line methods, CC <= 5)
- Commit with clear message describing the refactoring

## Safety Rules

- NEVER refactor without tests
- NEVER change behavior and structure in the same step
- NEVER skip the characterization test phase
- Commit after every successful step — small, reversible commits
- If unsure, revert and try a smaller step

## Prerequisite

- Smell identified (long method, large class, duplication, etc.)
- Existing tests cover the code being changed (or characterization tests will be written first)

## Verdict

After the final check passes, produce:
- **REFACTOR_COMPLETE**: All tests green, no behavior changes, code meets shape constraints.
- **REFACTOR_FAILED**: Tests broken or behavior changed. Revert to last good commit.

## Phase Output

```
Verdict: REFACTOR_COMPLETE / REFACTOR_FAILED
Next: /harness:code-review + /harness:security-review (parallel, single message)
Artifacts: [list of changed/created files]
Agent summaries: [engineer's 2-3 sentence contribution summary]
```
$ARGUMENTS
