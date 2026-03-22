---
task_id: three-sprints
phase: build
verdict: in_progress
timestamp: 2026-03-22T00:00:00Z
---

## Pipeline: Three Sprints — Orchestration Improvements

Started: 2026-03-22
Classification: Epic (3 compound features)
Branch: main
Scale: medium

## Phases
- Build: in_progress
- Review: pending
- Ship: pending

## Sprints
- Sprint 1 (A-D): Process fixes — intake CB, re-review mandatory, .gitignore delegation, pipeline-state dogfood
- Sprint 2 (E,F,H,L): Hook profiles, loop guard, AGENTS.md, ACI tool scoping
- Sprint 3 (G,I,J): Trajectory recording, harness-audit skill, hook test harness

## Key Files
- skills/intake/SKILL.md
- skills/pipeline/SKILL.md
- skills/project-setup/SKILL.md
- skills/harness-audit/SKILL.md (new)
- rules/pipeline-protocol.md
- orchestrator/agent-orchestration.md
- agents/code-reviewer.md, security-engineer.md, product-reviewer.md, architect.md
- hooks/hook-profile.sh (new), hooks/loop-guard.sh (new)
- hooks/subagent-stop-trajectory.sh (new), hooks/tests/test-hooks.sh (new)
- settings.json
- pipeline-state/README.md
