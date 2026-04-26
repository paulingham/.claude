---
task_id: opus47-thinking-defaults
phase: plan-validation
verdict: pending
timestamp: 2026-04-26T00:00:00Z
---

## Architect Plan Summary

### Approach: Hybrid Hook-Enforced Injection + Documentation Defaults

**Key decisions:**
1. `hooks/pre-agent-thinking.sh` (NEW): PreToolUse/Agent hook reads stdin JSON, delegates to `hooks/_lib/resolve-thinking.py` Python helper, emits `modified_tool_input` with computed `thinking` field
2. Python helper `resolve-thinking.py` (~50 lines): pure stdlib, resolves display/effort with logic for /debug detection, architect/boN escalation, explicit override preservation
3. Graceful degradation: if `modified_tool_input` is silently dropped by Claude Code, documentation in spawn templates provides the fallback belt-and-braces
4. 19 tests: 14 unit (resolve-thinking.py) + 5 integration (pre-agent-thinking.sh)
5. `settings.json` update via /harness-config (config change, not source file)

**Alternatives considered:**
- Pure documentation defaults — rejected (drift-prone at 50+ spawn sites)
- Wrapper skill `/with-thinking-defaults` — rejected (adds latency, same drift problem)

### Files Changed
- hooks/pre-agent-thinking.sh (NEW, ~25 lines bash)
- hooks/_lib/resolve-thinking.py (NEW, ~50 lines Python)
- tests/test_thinking_defaults.py (NEW, ~140 lines)
- settings.json (add hook entry to PreToolUse > Agent)
- CLAUDE.md (Thinking Defaults subsection)
- rules/parallel-dispatch-protocol.md (Best-of-N + template)
- agents/architect.md (Thinking Profile section)
- skills/build-implementation/SKILL.md (comment annotation)
- skills/best-of-n/config.json (thinking_defaults key)
- orchestrator/agent-orchestration.md (Thinking Injection section)
- orchestrator/parallel-dispatch-details.md (spawn snippet comments)
- README.md (hooks table)

### Test Coverage
- (a) Default injection: tests 1, 2, 17
- (b) /debug override: tests 3, 4
- (c) xhigh under critical/Budget>=7: tests 6, 7, 9
