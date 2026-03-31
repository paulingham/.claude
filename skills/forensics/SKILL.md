---
name: "forensics"
description: "Use when user wants to Post-incident investigation of pipeline runs. Reconstructs timelines from trajectory JSONL, analyzes anomalies (gaps, retries, long phases), and produces structured findings. Use after pipeline failures, unexpected rework, or to understand what went wrong."
argument-hint: "Task ID of the pipeline to investigate"
---

# Forensics

## What This Skill Does

Post-incident investigation of pipeline runs. Reconstructs timelines, detects anomalies, verifies artifact integrity, and produces a structured findings report. Evidence-based alternative to memory-based recollection.

## When to Invoke

- After a pipeline fails or requires >2 review rounds
- When reflection identifies issues but root cause is unclear
- When the user asks "what went wrong?"
- Automatically invoked by `/pipeline` Step 7 (Reflect) when failures occurred

## Process

### Step 1: Gather Evidence

```bash
# Trajectory file (agent events timeline)
cat ~/.claude/pipeline-state/{task-id}-trajectory.jsonl 2>/dev/null

# Pipeline state file
cat ~/.claude/pipeline-state/{task-id}-pipeline.md 2>/dev/null

# Debug state (if debugging loop was entered)
cat ~/.claude/pipeline-state/{task-id}-debug.md 2>/dev/null

# Git history during the pipeline
git log --oneline --since="{pipeline start}" --until="{pipeline end or now}"

# Diff summary
git diff --stat {start-commit}..HEAD
```

If trajectory JSONL is missing, reconstruct from pipeline state file and git log.

### Step 2: Timeline Reconstruction

Parse the trajectory JSONL (one JSON object per line) and build a timeline:

```markdown
### Timeline
| Time | Agent | Event | Duration | Notes |
|------|-------|-------|----------|-------|
| T+0m | software-engineer | agent_stopped | 12m | Build phase |
| T+12m | code-reviewer | agent_stopped | 4m | Review phase |
| T+16m | security-engineer | agent_stopped | 3m | Review phase |
| T+19m | — | gap | 7m | Possible compaction? |
| T+26m | software-engineer | agent_stopped | 8m | Fix for review findings |
```

Compute: total pipeline duration, per-phase duration, gap time.

### Step 3: Anomaly Detection

Flag any of the following:

| Anomaly | Detection Method | Significance |
|---------|-----------------|-------------|
| Long phase | Duration >2x median for that phase type | Possible complexity or rework |
| Retry | Same agent type spawned >1x in same phase | Fix cycle or failure |
| Timeline gap | >5 minutes between events | Context compaction or stall |
| Orphan agent | Agent in trajectory without matching task | Cleanup failure |
| Discipline violation | Files modified outside agent sessions | Orchestrator wrote code |
| Stale state | Pipeline state timestamp >24h old | Abandoned pipeline |

### Step 4: Artifact Integrity

Cross-reference pipeline state with git:

1. Are all files listed in pipeline state actually committed?
2. Does `git log` match the expected phase order?
3. Are there commits not accounted for in the pipeline state?
4. Do branch names follow the expected convention?

### Step 5: Root Cause Analysis

For each anomaly, propose a cause:
- "Phase X took 15 minutes because review found 3 findings requiring 2 fix cycles"
- "Gap at T+23m — context compaction occurred (PreCompact hook fired)"
- "Orphan agent — pipeline was interrupted before cleanup"

### Step 6: Produce Findings

Write `pipeline-state/{task-id}-forensics.md`:

```markdown
---
task_id: {task-id}
phase: forensics
verdict: {CLEAN / ANOMALIES_FOUND / INVESTIGATION_INCOMPLETE}
timestamp: {ISO 8601}
---

## Forensics: {task-id}

### Summary
{1-3 sentence overview of findings}

### Timeline
| Time | Agent | Event | Duration | Notes |
|------|-------|-------|----------|-------|

### Metrics
- Total duration: {Xm}
- Phase durations: Build {Xm}, Review {Xm}, Verify {Xm}, ...
- Review rounds: {N}
- Fix cycles: {N}
- Timeline gaps: {N} ({total gap time})

### Anomalies
| # | Type | Description | Root Cause |
|---|------|------------|------------|

### Artifact Integrity
- Pipeline state consistent with git: {yes/no}
- Files in state: {N}, Files in git: {M}
- Unaccounted commits: {list or none}

### Recommendations
- {recommendation 1}
- {recommendation 2}
```

## Phase Output

```
Verdict: CLEAN / ANOMALIES_FOUND / INVESTIGATION_INCOMPLETE
Next: Feed findings into /pipeline Step 7 (Reflect)
Artifacts: pipeline-state/{task-id}-forensics.md
```
$ARGUMENTS
