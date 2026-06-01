---
name: "workstream"
description: "Manage isolated workstreams for parallel feature development. Create, switch, list, and archive workstreams with isolated pipeline-state directories and branch conventions. Use when working on multiple features in parallel."
argument-hint: "create|switch|list|archive [workstream-name]"
---

# Workstream

## What This Skill Does

Manages isolated workstreams for parallel feature development. Each workstream gets its own pipeline-state directory, branch prefix convention, and lifecycle.

## When to Invoke

- Starting work on a second feature while another is in-progress
- Organizing parallel development across multiple features
- Resuming work and need to see all active workstreams

## Commands

### create {name}

Creates a new workstream:

1. Create directory: `pipeline-state/workstreams/{name}/`
2. Create metadata: `pipeline-state/workstreams/{name}/workstream.md`

```markdown
---
name: {name}
status: active
created: {ISO 8601}
branch_prefix: feat/{name}/
---

## Workstream: {name}

### Active Pipelines
(none yet)

### Completed Pipelines
(none yet)
```

3. Report: "Workstream `{name}` created. Pipelines started within this workstream will use branch prefix `feat/{name}/` and store state in `pipeline-state/workstreams/{name}/`."

### switch {name}

Switches active workstream context:

1. Verify `pipeline-state/workstreams/{name}/workstream.md` exists
2. Read workstream metadata for branch prefix and status
3. List active pipelines in the workstream
4. Report current state

### list

Lists all workstreams and their status:

```bash
ls ~/.claude/pipeline-state/workstreams/*/workstream.md 2>/dev/null
```

Output format:
```
Active workstreams:
  auth/ — 1 active pipeline (login-page, phase: review)
  payments/ — 0 active pipelines

Archived workstreams:
  onboarding/ — archived 2026-03-28

Ungrouped pipelines:
  hotfix-nav — phase: build
```

### archive {name}

Archives a completed workstream:

1. Verify all pipelines in the workstream are completed (no `in_progress` status)
2. Create `pipeline-state/workstreams/archive/` if it doesn't exist
3. Move `pipeline-state/workstreams/{name}/` to `pipeline-state/workstreams/archive/{name}/`
4. Update workstream.md status to `archived` with timestamp

## Integration with Pipeline

When a workstream is active, the pipeline skill stores state files under a per-task subdirectory inside the workstream directory (DUAL_PATH soak — see `protocols/pipeline-protocol.md` § Structured Pipeline State):

- Pipeline state: `pipeline-state/workstreams/{name}/{task-id}/pipeline.md`
- Build results: `pipeline-state/workstreams/{name}/{task-id}/build.md`
- Debug state: `pipeline-state/workstreams/{name}/{task-id}/debug.md`
- Discussion: `pipeline-state/workstreams/{name}/{task-id}/discussion.md`
- Trajectory: `pipeline-state/workstreams/{name}/{task-id}/trajectory.jsonl`

Legacy flat form (`pipeline-state/workstreams/{name}/{task-id}-{phase}.md`) remains readable during the 90-day soak window but is never written by new code. Path resolution always goes through `hooks/_lib/pipeline_state_paths.py` (or `pipeline-state-paths.sh` from bash).

Branch convention: `feat/{workstream}/{task}` (e.g., `feat/auth/login-page`)

## Integration with Pipeline Resume

`/harness:pipeline-resume` uses the canonical four-glob discovery sequence (see `skills/pipeline-resume/SKILL.md` Step 1). Workstream-nested pipelines (`pipeline-state/workstreams/{name}/{task-id}/pipeline.md`) are returned alongside root-level pipelines (`pipeline-state/{task-id}/pipeline.md`). When the same `task_id` collides between root and workstream, **workstream wins**; ties within a layout class break by mtime.

Display groups results for the user:
- Workstream-nested pipelines (grouped by workstream name)
- Root-level (ungrouped) pipelines
- Active debug sessions (both layouts)

## Phase Output

```
Verdict: WORKSTREAM_CREATED / WORKSTREAM_LISTED / WORKSTREAM_ARCHIVED
Next: Start a pipeline within the workstream
Artifacts: pipeline-state/workstreams/{name}/workstream.md
```
$ARGUMENTS
