---
task_id: opus47-thinking-defaults
phase: intake
classification: feature
complexity_budget: 12
critical: false
effort_override: high
architect_effort: xhigh
multi_repo: false
timestamp: 2026-04-26T00:00:00Z
---

## Task Summary
Configure Opus 4.7 thinking defaults harness-wide:
1. Every orchestrator agent-spawn defaults to thinking.display="omitted"
2. Exception: /debug skill uses display="text"
3. Architect + Best-of-N Build Team use effort="xhigh" when critical=true OR Budget>=7
4. Default effort="high" otherwise
5. Apply to both Agent tool (subagent) and TaskCreate (team teammate) dispatch paths
6. PreAgent hook enforces display="omitted" injection; logs to metrics/{session}/hook-injections.jsonl
7. Tests: (a) default injection, (b) /debug override, (c) architect xhigh under critical/Budget>=7

## Files to Touch
- CLAUDE.md (Quick Reference section — document defaults)
- rules/parallel-dispatch-protocol.md (Best-of-N section + teammate prompt template)
- agents/architect.md (xhigh trigger condition)
- skills/build-implementation/SKILL.md (effort default in spawn template)
- skills/best-of-n/config.json (per-candidate effort field)
- orchestrator/agent-orchestration.md (spawn template defaults)
- orchestrator/parallel-dispatch-details.md (team dispatch procedure)
- hooks/pre-agent-thinking.sh (NEW — default injection hook)
- settings.json (register new PreToolUse hook)
- tests/test_thinking_defaults.py (NEW — unit tests)
- README.md (update if behavior-visible)

## Complexity Budget
- Scope=3 (11+ files), Ambiguity=1 (fully specified), Context=3 (system-wide),
  Novelty=2 (hook patterns exist), Coordination=3 (cross-cutting: hooks+agents+skills+docs+tests)
- Total: 12 → plan first, autonomous plan validation

## Routing
Entry: /pipeline → Plan → [autonomous challengers] → Build → Review → Final Gate → Ship
