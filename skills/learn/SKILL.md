---
name: "Learn"
description: "Analyze recent session observations and extract instincts (learned patterns). Reads observations.jsonl, identifies recurring patterns, creates or updates instinct files with confidence scoring. Invoke periodically or at session end."
argument-hint: "Optional: project path or 'global'"
---

# Learn

## What This Skill Does

Analyzes accumulated tool-use observations from sessions and extracts "instincts" — atomic learned patterns with confidence scoring. Instincts are project-scoped by default and promote to global when seen across multiple projects.

Inspired by ECC's continuous learning system. The key insight: hooks observe 100% of tool usage (deterministic), not 50-80% (skill-based). Patterns emerge from consistent behavior, not explicit instructions.

## When to Invoke

- Periodically (e.g., every 5-10 sessions, or weekly)
- After a pipeline completes (part of reflection)
- Manually when you want to review what's been learned
- Automatically via `/pipeline` Step 7 (Reflect) when observations exist

## Process

### 1. Identify Project

Determine the project hash (same as observation-capture hook):
```bash
git remote get-url origin 2>/dev/null | md5 -q || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

### 2. Read Observations

```bash
cat ~/.claude/learning/{project-hash}/observations.jsonl
```

Parse the last N sessions' worth of observations (default: last 500 entries or 7 days).

### 3. Pattern Detection

Identify recurring patterns:

| Pattern Type | Detection Method | Example |
|-------------|-----------------|---------|
| **Tool preference** | Same tool used >80% of the time for a file type | "Always uses Edit (not Write) for .ts files" |
| **File access pattern** | Same files always read together | "Always reads types.ts before editing service.ts" |
| **Repeated decisions** | Same approach chosen across sessions | "Always adds error boundary when creating React components" |
| **Test patterns** | Consistent test file naming/structure | "Uses describe/it blocks, never test()" |
| **Avoided patterns** | Things consistently NOT done | "Never modifies .eslintrc (config protection)" |

### 4. Create or Update Instincts

For each detected pattern, check `~/.claude/learning/instincts/`:

**If instinct exists** (matching pattern):
- Bump `evidence_count`
- Update `last_seen` timestamp
- Adjust confidence: `+0.1` per new evidence, max `0.9`

**If new pattern**:
- Create `~/.claude/learning/instincts/instinct-{hash}.md`:

```markdown
---
id: instinct-{hash}
confidence: 0.3
domain: {testing|code-style|git|debugging|workflow|architecture}
scope: project
project: {project-hash}
created: {ISO 8601}
evidence_count: 1
last_seen: {ISO 8601}
---

## Pattern
{One-sentence description of the learned behavior}

## Evidence
- {date}: {observation that triggered this instinct}
```

### 5. Prune Stale Instincts

- Instincts not seen in 30+ days: reduce confidence by 0.1 per week of absence
- Instincts at confidence 0.0: delete
- Report pruned instincts

### 6. Promote to Global

Instincts meeting ALL criteria:
- Confidence >= 0.8
- Seen in 2+ different projects
- Evidence count >= 5

Promote by changing `scope: global` and `project: global`.

### 7. Report

```
Learning Report:
- Observations analyzed: N (from {date} to {date})
- New instincts created: N
- Instincts updated: N (confidence changes)
- Instincts pruned: N
- Instincts promoted to global: N

Top instincts by confidence:
  [0.85] Always use describe/it in tests (domain: testing)
  [0.72] Read types.ts before editing services (domain: workflow)
  [0.50] Prefer named exports over default exports (domain: code-style)
```

## Phase Output

```
Verdict: LEARNED / NO_NEW_PATTERNS / NO_OBSERVATIONS
Next: Continue with normal work
Artifacts: [list of instinct files created/updated/pruned]
```
