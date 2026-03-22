# Pipeline State

Structured phase results for in-progress pipelines. See `rules/pipeline-protocol.md` § Structured Pipeline State for the full convention.

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
{"timestamp":"2026-03-22T10:00:00Z","agent":"software-engineer","event":"agent_stopped","task_id":"auth-feature","phase":"build","outcome":"committed"}
```

Trajectory files enable:
- **Audit trail**: what happened, in what order, by which agents
- **Replay**: reproduce a pipeline run from its trajectory
- **Learning**: identify patterns in successful vs failed pipeline runs

Set `CLAUDE_PIPELINE_TASK_ID` in your environment or at pipeline start to activate trajectory recording. The `subagent-stop-trajectory.sh` hook appends to the trajectory automatically on every agent completion.

### Cleanup

After a pipeline completes, delete both the state file and the trajectory file:
```bash
rm ~/.claude/pipeline-state/{task-id}-pipeline.md
rm ~/.claude/pipeline-state/{task-id}-trajectory.jsonl
```

Run `/harness-audit` to find stale files (>7 days old).
