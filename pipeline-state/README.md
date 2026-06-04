# Pipeline State

> **Canonical location (post-migration)**: Pipeline state is stored at
> `${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/pipeline-state/` (HARNESS_DATA).
> The `pipeline-state/` directory in this repo is **legacy read-tolerated** for 90 days
> from the merge of the relocate-pipeline-state-writes PR
> (run `git log --format=%aI -1 <merge-commit>` for exact date).
> After that date this directory contains no active state — use `detect-stale-pipeline-state.sh`
> to confirm before removal.
>
> **Concurrent sessions**: relocating pipeline-state to `$HOME/.claude/pipeline-state` moves
> cross-session contention from the git-tracked repo root to a shared home-dir location. The
> risk is lower (no git operations touch it), but concurrent sessions sharing the same `$HOME`
> share the directory. For fully isolated concurrent setups, set a per-session
> `CLAUDE_PLUGIN_DATA` pointing to a session-scoped directory.

Structured phase results for in-progress pipelines. See `protocols/pipeline-protocol.md` § Structured Pipeline State for the full convention.

## Quick Reference

- **Naming**: `{task-id}-{phase}.md`
- **Lifecycle**: created by phase, read by next phase, deleted after pipeline completes
- **Purpose**: survives context compaction, enables inter-phase communication
- **Cleanup**: orchestrator deletes all files for a task after completion

## Example

```
pipeline-state/
  auth-feature-build.md      # Build phase results
  auth-feature-review.md     # Review phase results (code + security)
  auth-feature-verify.md     # Verification tier results
```

Files in this directory are transient — they should not accumulate across sessions. If you see state files from a previous session, check whether the pipeline was abandoned or needs resumption.

## Trajectory Files

Each pipeline run also produces a trajectory file: `{task-id}-trajectory.jsonl`

Each line is a JSON record of an agent event:
```json
{"timestamp":"2026-03-22T10:00:00Z","agent":"software-engineer","event":"agent_stopped","task_id":"auth-feature"}
```

Trajectory files enable:
- **Audit trail**: what happened, in what order, by which agents
- **Replay**: reproduce a pipeline run from its trajectory
- **Learning**: identify patterns in successful vs failed pipeline runs

Set `CLAUDE_PIPELINE_TASK_ID` in your environment or at pipeline start to activate trajectory recording. The `subagent-stop-trajectory.sh` hook appends to the trajectory automatically on every agent completion.

### Cleanup

After a pipeline completes, delete both the state file and the trajectory file
(see `skills/pipeline/SKILL.md` Step 7d for the canonical snippet using `state_dir`):
```bash
state_dir="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/pipeline-state"
rm "$state_dir/{task-id}-pipeline.md"
rm "$state_dir/{task-id}-trajectory.jsonl"
```

Run `/harness-audit` to find stale files (>7 days old).

## Debug State Files

- **Naming**: `{task-id}-debug.md`
- **Created by**: `/debug` skill (invoked from `/bug-fix` for complex bugs)
- **Purpose**: Persistent hypothesis tracking for multi-session debugging
- **Cleanup**: Orchestrator updates status to `resolved` and deletes after pipeline completion

## Discussion Files

- **Naming**: `{task-id}-discussion.md`
- **Created by**: `/intake` skill (Step 2b Exploration Gate, when Ambiguity >= 2)
- **Purpose**: Persists clarifying questions, user decisions, and approach validation
- **Consumed by**: Architect during Plan phase
- **Cleanup**: Deleted with other pipeline-state files after pipeline completion

## Forensics Files

- **Naming**: `{task-id}-forensics.md`
- **Created by**: `/forensics` skill (post-incident investigation)
- **Purpose**: Timeline reconstruction, anomaly detection, artifact integrity checks
- **Cleanup**: Deleted with other pipeline-state files after pipeline completion

## Workstreams

For parallel feature development, pipelines can be grouped into workstreams:

```
pipeline-state/
  workstreams/
    auth/
      workstream.md              # Workstream metadata
      login-page-pipeline.md     # Pipeline state (scoped)
      login-page-build.md
    payments/
      workstream.md
  hotfix-nav-pipeline.md         # Ungrouped pipeline (default)
```

Create workstreams via `/workstream create {name}`. Each workstream has its own directory, branch prefix convention, and lifecycle.
