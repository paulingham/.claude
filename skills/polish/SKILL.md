---
name: "polish"
description: "Use when user wants to Lightweight mechanical cleanup pass between Build and Review. Fixes naming, dead code, import ordering, comment quality — the things self-review misses due to author bias. Uses Haiku for cost efficiency."
context: fork
agent: software-engineer
model: haiku
---

# Polish

## What This Skill Does

A fast, cheap cleanup pass that runs between Build and Review. Fixes only mechanical issues — naming, dead code, import ordering, commented-out blocks, unused variables. Does NOT touch design, architecture, or logic.

The insight: self-review is author-biased. The same agent that wrote the code is the worst judge of its own sloppiness. A separate agent with fresh eyes catches mechanical issues the builder missed.

## When to Invoke

- After Build completes (BUILD_COMPLETE) and before Review dispatch
- Only when Complexity Budget >= 7 (non-trivial tasks)
- Skipped for micro/small pipelines (Budget 5-6)
- Invoked by the pipeline orchestrator, not manually

## Dispatch

Spawn as subagent with `isolation: "worktree"`, model `haiku`, max 15 turns:

```
Agent({
  subagent_type: "software-engineer",
  isolation: "worktree",
  model: "haiku",
  prompt: "Read ~/.claude/skills/polish/SKILL.md and execute it fully.
    Read ~/.claude/agents/software-engineer.md for your role definition.
    Context: branch [branch], base main.
    Changed files: [git diff --name-only main...HEAD]"
})
```

## Process

### 1. Read Changed Files

```bash
git diff --name-only main...HEAD
```

Read each changed source file (skip tests, configs, lock files).

### 2. Fix Mechanical Issues Only

For each file, check and fix:
- **Dead imports**: imported but never used
- **Commented-out code**: remove (git has history)
- **Unused variables**: declared but never referenced
- **Import ordering**: group by stdlib, external, internal
- **Naming clarity**: single-letter variables (except loop counters), abbreviations, misleading names
- **Inconsistent formatting**: mixed quote styles, trailing whitespace, inconsistent semicolons

### 3. Do NOT Touch

- Design decisions or architecture
- Logic or control flow
- Test structure or assertions
- Any behavioral change whatsoever

If unsure whether a change is mechanical or behavioral, skip it.

### 4. Commit and Report

```bash
git add [specific files]
git commit -m "chore: polish — mechanical cleanup"
```

Report:
```
Polished N files:
- file.ts: removed 2 dead imports, fixed variable name
- other.ts: removed commented-out code block
```

## Phase Output

```
Verdict: POLISHED / NO_CHANGES_NEEDED
Next: /harness:code-review + /harness:security-review (parallel)
Artifacts: [list of files cleaned, changes per file]
```
