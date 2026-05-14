---
id: instinct-runtime-guard-stale-cleanup
confidence: 0.50
category: fragility
domain: workflow
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [pipeline-orchestrator]
applies_to_roles: [pipeline-orchestrator]
source: observation
created: 2026-05-14T00:00:00Z
evidence_count: 1
last_seen: 2026-05-14T00:00:00Z
---

## Pattern
The `runtime-guard.sh` PreToolUse hook scans `~/.claude/metrics/{session}/subagent-runtimes/*.start` files and blocks Bash/Write/Edit tools when ANY .start file's `(now - ts)` exceeds the cap (1800s subagent / longer teammate). Stale .start files from prior sessions ACCUMULATE across pipelines — agents that crash or exit abnormally leave .start files behind, which then trigger spurious blocks on the next Bash/Write/Edit invocation in a fresh session.

**Why**: the hook's `_rg_scan_dir` (`hooks/_lib/runtime-guard-check.sh`) iterates `$dir/*.start` and emits exit 2 on any over-cap file — there's no PostToolUse cleanup hook that reliably removes .start files when agents complete cleanly. A stale .start from 22 hours ago blocks the next Edit even on a brand-new pipeline.

**How to apply**: as the pipeline orchestrator, if you see `BLOCKED: subagent runtime cap exceeded` mid-pipeline, run:
```bash
find $HOME/.claude/metrics -path "*/subagent-runtimes/*.start" -mmin +30 -delete -print | wc -l
```
This removes all .start files older than the cap (30 min). It is safe because (a) any agent still actually running would have its .start refreshed periodically, and (b) the cleanup is per-file with `-delete`, not `rm -rf`.

## Evidence
- 2026-05-14: iron-law-2-freshness-hook pipeline mid-Plan-Validation cleanup blocked Edit on plan-validation.md; 95 stale .start files across 100+ session subdirectories; one-liner cleared the block.
