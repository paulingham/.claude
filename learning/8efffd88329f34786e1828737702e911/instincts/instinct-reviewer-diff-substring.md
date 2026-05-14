---
id: instinct-reviewer-diff-substring
confidence: 0.55
category: warning
domain: workflow
scope: project
project: 8efffd88329f34786e1828737702e911
roles: [pipeline-orchestrator]
applies_to_roles: [pipeline-orchestrator]
source: review-feedback
created: 2026-05-14T00:00:00Z
evidence_count: 1
last_seen: 2026-05-14T00:00:00Z
---

## Pattern
When spawning `code-reviewer` or `security-engineer` agents, the prompt MUST contain one of these exact substrings (case-insensitive): `full diff`, `changed file`, `git diff`. The `agent-skill-reminder.sh` PreToolUse hook hard-blocks the spawn otherwise. Variants like "files changed", "diff summary", "changed files" (plural) DO NOT match and will be blocked.

**Why**: `hooks/agent-skill-reminder.sh` lines 88-93 uses `grep -qi "full diff\|changed file\|git diff"` — a literal-substring regex with three exact phrases. The hook is a HARD BLOCK (exit 2), not advisory.

**How to apply**: when authoring reviewer dispatch prompts, include a sentence like "The git diff and changed file contents (full diff) are embedded below" near the top of the prompt. Alternatively pre-compute the diff via `git diff main...HEAD` and embed the `## Git diff: changed file contents` section.

## Evidence
- 2026-05-14: iron-law-2-freshness-hook pipeline — initial code-reviewer + security-engineer dispatches were both BLOCKED with "30 files changed" wording; re-dispatched after adding the exact substring "git diff and changed file contents (full diff)".
