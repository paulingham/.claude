---
mode: code-archaeology
task_id: model-demotion-pass-2026-05
generated: 2026-05-14T12:00:00Z
---

# Code-Archaeology Recon — model-demotion-pass-2026-05

Synthetic-but-realistic replay of `architect-context-recon` mode=`code-archaeology` output, captured for slice-C fixture testing. Asserts shape (≥3 findings with `file:line` citations), not provenance.

## Findings

### Finding 1: Sonnet-executor + Opus-advisor pairing precedent
- **What**: Two reviewer agents already declare `executor:` and `advisor:` Opus pairs; this is the canonical advisor-mode shape.
- **Where**: agents/code-reviewer.md:9, agents/security-engineer.md:11
- **Why it matters for the plan**: Demotion ACs must preserve the advisor field even when flipping the executor — see protocols/advisor-mode.md:42 for the contract.

### Finding 2: Haiku-solo precedent for transcription-only roles
- **What**: `session-memory-updater` is the in-tree Haiku precedent; its frontmatter sets `model: haiku` plus `executor: claude-haiku-4-5-20251001` plus the explicit advisor-rationale comment.
- **Where**: agents/session-memory-updater.md:7, agents/session-memory-updater.md:10
- **Why it matters for the plan**: Any new Haiku demotion should mirror this exact frontmatter shape so the contract test in tests/test_agent_frontmatter.py:46 stays green.

### Finding 3: Existing executor frontmatter contract test
- **What**: A unittest already locks the executor/advisor frontmatter contract for every agent file under `agents/*.md`; demotions that omit `executor:` or break the `claude-` prefix will fail this gate.
- **Where**: tests/test_agent_frontmatter.py:46, tests/test_agent_frontmatter.py:57
- **Why it matters for the plan**: Run this test BEFORE committing any demotion — it is the cheapest signal that the frontmatter shape stayed valid.

### Finding 4: Cost-record schema for leading indicator
- **What**: Per-spawn cost records emit one JSONL row per Agent spawn keyed by `agent_role` and `model`; the post-flip leading indicator (Sonnet-only code-reviewer at CB<6) reads this file.
- **Where**: hooks/cost-record.sh:23, hooks/pre-agent-thinking.sh:91
- **Why it matters for the plan**: The baseline cost report's leading indicator must name this exact path so post-flip verification is a one-liner grep.

## Anti-Findings (searched, found nothing — flag for greenfield design)

- Per-task-class model routing — searched in orchestrator/agent-orchestration.md and skills/dispatch/; no precedent for routing planning-agent at spawn time. Model is set at frontmatter parse only.
- Runtime advisor handoff for poll-loop agents — searched in agents/planning-agent.md history; no advisor handoff pattern exists for long-lived agents. Demoting the executor is the only lever.

## Recommended Architect Read Order (most-relevant first)

1. agents/session-memory-updater.md
2. tests/test_agent_frontmatter.py
3. protocols/advisor-mode.md
