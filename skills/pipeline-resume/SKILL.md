---
name: "pipeline-resume"
description: "Use when user wants to Resume an in-progress pipeline from pipeline-state/ files. Validates state schema, determines current phase, and re-enters the pipeline at the correct point."
argument-hint: "Optional: task ID to resume (auto-detects if only one active pipeline)"
---

# Pipeline Resume

## What This Skill Does

Detects and resumes in-progress pipelines from structured state files in `pipeline-state/`. Handles the case where a pipeline was interrupted by context compaction, session end, or agent failure.

## When to Invoke

- At session start when `pipeline-state/` contains active state files
- When user asks to continue previous work
- When the SessionStart hook detects in-progress pipelines

## Process

### Step 1: Scan for Active Pipelines

The DUAL_PATH soak (see `rules/pipeline-protocol.md` § Structured Pipeline State) means readers MUST tolerate both the new per-task-subdir layout (`pipeline-state/{task-id}/pipeline.md`) and the legacy flat form (`pipeline-state/{task-id}-pipeline.md`). Use the canonical four-glob discovery sequence (encapsulated in `_psp_find_active_pipelines` from `hooks/_lib/pipeline-state-paths.sh`):

```bash
# 1. New layout, root
find ~/.claude/pipeline-state -maxdepth 2 -mindepth 2 -name "pipeline.md" \
  -not -path "*/workstreams/*" -not -path "*/health-reports/*"
# 2. New layout, workstream
find ~/.claude/pipeline-state/workstreams -maxdepth 3 -mindepth 3 -name "pipeline.md"
# 3. Legacy layout, root
find ~/.claude/pipeline-state -maxdepth 1 -name "*-pipeline.md"
# 4. Legacy layout, workstream
find ~/.claude/pipeline-state/workstreams -maxdepth 2 -name "*-pipeline.md"
```

Dedup the union by `task_id` with **workstream-wins precedence**; tie-break by mtime (fresher wins; ties favour the new layout). The shorthand glob `pipeline-state/*/pipeline.md` matches the new-layout root form — combine with the other three for full coverage.

Always use the helper (`_psp_find_active_pipelines`) rather than open-coding the globs — the helper handles exclusion of `health-reports/` and `workstreams/` siblings.

Also scan for debug state and discussion files (DUAL_PATH — same dedup
rules as above; same `health-reports/` exclusion):
```bash
# New layout (root + workstream-nested)
find ~/.claude/pipeline-state \( -name "debug.md" -o -name "discussion.md" \) \
  -not -path "*/health-reports/*" 2>/dev/null
# Legacy layout
ls ~/.claude/pipeline-state/*-debug.md 2>/dev/null
ls ~/.claude/pipeline-state/*-discussion.md 2>/dev/null
ls ~/.claude/pipeline-state/workstreams/*/*-debug.md 2>/dev/null
ls ~/.claude/pipeline-state/workstreams/*/*-discussion.md 2>/dev/null
```

Also scan workstream metadata:
```bash
ls ~/.claude/pipeline-state/workstreams/*/workstream.md 2>/dev/null
```

Display results grouped:
```
Active workstreams:
  auth/ — 1 active pipeline (login-page, phase: review)
  payments/ — 0 active pipelines

Ungrouped pipelines:
  hotfix-nav — phase: build

Active debug sessions:
  task-123 — 3 hypotheses, 2 fix attempts
```

If multiple active pipelines found, list them and ask user which to resume.
If one found, resume automatically.
If none found, report "No active pipelines" and exit.

### Step 2: Validate State File Schema

Read the pipeline state file and verify required frontmatter fields:

```yaml
---
task_id: [required — string]
phase: [required — build|review|verify|test|accept|ship]
verdict: [required — in_progress|completed|failed]
timestamp: [required — ISO 8601]
---
```

Also verify the body contains:
- Pipeline name/description
- Scale classification (micro/small/medium/large)
- Branch name
- Phase status list (which phases completed, which pending)
- Key files list (what was created/modified)

If any required field is missing, warn and ask user to confirm the state is valid or start fresh.

### Step 3: Determine Resume Point

Read the phase status list from the state file:

```
- Build: completed
- Review: completed (both APPROVE)
- Verify: in_progress  ← resume here
- Test: pending
- Accept: pending
- Ship: pending
```

The resume point is the first phase that is `in_progress` or `pending` after all `completed` phases.

### Step 4: Verify Branch and Working Tree

```bash
# Verify we're on the correct branch
git branch --show-current

# Check for uncommitted changes
git status --porcelain

# Verify last commit matches expectations
git log --oneline -3
```

If the branch doesn't match the state file, warn the user.
If there are uncommitted changes, warn before proceeding.

### Step 5: Re-Enter Pipeline

Update the state file to mark the resume:
```yaml
timestamp: [current ISO 8601]
resumed_at: [current ISO 8601]
resumed_from: [phase name]
```

Then invoke `/pipeline` with context:
- Current phase to resume from
- Prior phase verdicts and artifacts
- Key files from previous phases
- Branch name

The pipeline continues from the resume point, skipping completed phases.

## Phase Output

```
Verdict: RESUMED / NO_ACTIVE_PIPELINE / STATE_INVALID
Next: Continue pipeline from [phase name]
Artifacts: [state file path, resume point, prior phase verdicts]
```
$ARGUMENTS
