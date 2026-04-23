---
name: "learn"
description: "Use when user wants to Analyze recent session observations and extract instincts (learned patterns). Reads observations.jsonl, identifies recurring patterns, creates or updates instinct files with confidence scoring. Invoke periodically or at session end."
argument-hint: "Optional: project path or 'global'"
---

# Learn

## What This Skill Does

Analyzes accumulated tool-use observations, pipeline analytics, and review findings to extract "instincts" — atomic learned patterns with confidence scoring. Instincts modify agent behavior in future pipelines, creating a compounding improvement loop.

The key insight: hooks observe 100% of tool usage (deterministic). Pipeline analytics capture every phase outcome. Review findings reveal preventable issues. Patterns emerge from consistent behavior across sessions.

## When to Invoke

- **Automatically** via `/pipeline` Step 7c (Reflect) after every pipeline completion
- Periodically (e.g., every 5-10 sessions, or weekly)
- Manually when you want to review what's been learned

## Process

### 1. Identify Project & Bootstrap Instincts Dir

Resolve the project hash and ensure the per-project instincts directory exists. `mkdir -p` is idempotent — this must succeed on first `/learn` invocation in a project (when no instincts have been created yet) without erroring.

```bash
source "$HOME/.claude/hooks/_lib/project-hash.sh"
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Idempotent: safe to run on first invocation (no instincts yet) and on repeat runs.
mkdir -p "$HOME/.claude/learning/$PROJECT_HASH/instincts"
```

On first run in a project, this directory will be empty. `/learn` must still succeed — step 5 will populate it from the accumulated observations.

### 2. Read Data Sources

Three data sources feed pattern detection:

#### 2a. Enriched Observations
```bash
cat ~/.claude/learning/{project-hash}/observations.jsonl
```
Parse the last 500 entries or 7 days. Each record contains:
`{timestamp, session_id, tool, file, project, project_hash, phase, agent_role, outcome}`

#### 2b. Pipeline Analytics
```bash
cat ~/.claude/metrics/pipelines.jsonl | jq 'select(.project == "{project-name}")'
```
Last N pipeline records for this project. Each contains: phase verdicts, review rounds, agent counts, complexity budget.

#### 2c. Review Findings (Current Pipeline Only)
If invoked from pipeline Reflect step, read the review phase state file:
```bash
cat ~/.claude/pipeline-state/{task-id}-review.md
```
Extract findings with their severity and category.

### 3. Pattern Detection

Analyze across all three data sources:

| Pattern Type | Signal | Data Source | Example Instinct |
|---|---|---|---|
| **Rework hotspots** | Same files appear in review findings across 3+ pipelines | Pipeline analytics + review state | "Auth module: always validate token expiry before storage" |
| **Phase bottlenecks** | One phase consistently >40% of total review rounds | Pipeline analytics | "Review is the bottleneck — pre-address SOLID violations in build" |
| **Review patterns** | Same finding category in >30% of reviews | Pipeline analytics + review state | "This project: always check for missing error boundaries in React" |
| **Tool preference** | Same tool used >80% for a file type within a phase | Observations | "During build: always Read types.ts before editing services" |
| **File access clusters** | Same files consistently accessed together in same session | Observations (session_id grouping) | "Routes and middleware are always modified together" |
| **Error-prone areas** | Files with outcome=error appearing >3x | Observations | "Config parsing is fragile — add defensive checks" |
| **Phase-specific patterns** | Consistent behavior within a specific pipeline phase | Observations (phase field) | "During review: always check test coverage on new files" |
| **Model efficiency** | Phase outcomes identical across model tiers | Pipeline analytics | "Sonnet handles DB migration reviews as well as Opus" |
| **Test gaps** | Bug fixes correlate with specific file patterns | Pipeline analytics + observations | "Files matching **/hooks/*.ts have 3x the bug rate" |

### 4. Classify Review Findings (Backward Feedback)

For each review finding from the current pipeline, classify:

| Classification | Criteria | Action |
|---|---|---|
| **Preventable by build** | Standard pattern violation (missing validation, SOLID, naming) | Create instinct tagged `role: [software-engineer, frontend-engineer]` |
| **Review-level only** | Architectural concern, cross-cutting issue, subtle bug | No build instinct — this is the reviewer's value-add |
| **Recurring preventable** | Same preventable finding in 3+ pipelines | Promote instinct confidence by +0.2 (urgent pattern) |

Preventable findings become build-targeted instincts: "In {project}, always {check/do X} during build because {review consistently catches Y}."

### 5. Create or Update Instincts

Project-scoped instincts live in `~/.claude/learning/{project-hash}/instincts/`. Global (promoted) instincts live in `~/.claude/learning/instincts/global/`. Check both when looking for existing matches, but create new project-scoped instincts in the per-project directory.

**If instinct exists** (matching pattern, either location):
- Bump `evidence_count`
- Update `last_seen` timestamp
- Adjust confidence: `+0.1` per new evidence, max `0.95`
- Recurring preventable findings: `+0.2` instead of `+0.1`

**If new pattern**, create `~/.claude/learning/{project-hash}/instincts/instinct-{hash}.md`:

```markdown
---
id: instinct-{hash}
confidence: 0.3
domain: {testing|code-style|architecture|workflow|performance|security}
scope: project
project: {project-hash}
roles: [software-engineer, code-reviewer]
source: {observation|pipeline-analytics|review-feedback}
created: {ISO 8601}
evidence_count: 1
last_seen: {ISO 8601}
---

## Pattern
{One-sentence actionable description: "Always X when Y because Z"}

## Evidence
- {date}: {observation/finding that triggered this instinct}
```

**Instinct fields**:
- `roles`: Which agent roles this instinct applies to. Used by the orchestrator to filter instincts when spawning agents (see orchestrator/agent-orchestration.md).
- `source`: Where this instinct came from. `observation` = tool usage patterns. `pipeline-analytics` = phase-level metrics. `review-feedback` = backward feedback from reviewer findings.
- `domain`: Category for grouping and reporting.

### 6. Prune Stale Instincts

- Instincts not seen in 30+ days: reduce confidence by 0.1 per week of absence
- Instincts at confidence <= 0.0: delete
- Report pruned instincts

### 7. Promote to Global

Instincts meeting ALL criteria:
- Confidence >= 0.8
- Seen in 2+ different projects (different `project` values in observations/analytics)
- Evidence count >= 5

Promote by:
1. Copy to `~/.claude/learning/instincts/global/` subdirectory
2. Set `scope: global` and `project: global`
3. Global instincts are injected into ALL agent prompts regardless of project

### 8. Identify System Improvements (Continuous Self-Improvement)

Beyond instincts, analyze the data for system-level improvement proposals:

| Signal | Proposal |
|---|---|
| A hook fires frequently but never blocks (>50 no-ops) | "Consider moving {hook} to lazy evaluation" |
| Review rounds consistently > 1 for a project | "Build agents need stronger pre-review checklist for {project}" |
| Same phase fails across projects | "Skill {X} may need updating — fails in {N}% of pipelines" |
| Pipeline cycle time trending up | "Investigate bottleneck: {phase} taking {N}% longer than baseline" |

System proposals are surfaced to the user during the Reflect report, not auto-applied.

### 9. Report

```
Learning Report:
- Observations analyzed: N (from {date} to {date})
- Pipeline analytics reviewed: N pipelines
- Review findings classified: N (M preventable, K review-level)

Instinct Changes:
- New instincts created: N
  - [0.30] {pattern description} (source: {source}, roles: {roles})
- Instincts updated: N (confidence changes)
  - [0.50 → 0.60] {pattern description}
- Instincts pruned: N
- Instincts promoted to global: N

Top instincts by confidence:
  [0.85] Always validate input at controller boundary (domain: security, roles: [software-engineer])
  [0.72] Read types.ts before editing services (domain: workflow, roles: [software-engineer])
  [0.50] Check for N+1 queries in ActiveRecord scopes (domain: performance, roles: [software-engineer, code-reviewer])

System Proposals: (if any)
  - {proposal description}
```

## Phase Output

```
Verdict: LEARNED / NO_NEW_PATTERNS / NO_OBSERVATIONS
Next: Continue with normal work
Artifacts: [list of instinct files created/updated/pruned]
System proposals: [list, if any]
```
$ARGUMENTS
