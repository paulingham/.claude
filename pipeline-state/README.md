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
