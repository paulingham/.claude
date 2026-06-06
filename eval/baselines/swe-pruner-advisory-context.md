---
advisory_mode: true
eval_pass_rate: 1.00
eval_suite: swe-pruner-unit-integration
eval_n: 121
---

# SWE-Pruner Advisory Context Filter — Eval Baseline

## Scope Transparency (Option A)

The pruner operates on the orchestrator-assembled spawn prompt
(`tool_input.prompt` at PreToolUse Agent) — scratchpad, protocols,
session memory, role-doc, and instinct injections. It does NOT operate
on source files the subagent subsequently Reads; that seam is invisible
to any orchestrator hook. A future Option B (in-subagent library) is a
materially different architecture requiring its own intake.

## Advisory Mode

This baseline records the advisory-only phase: the hook LOGS proposed
drops to JSONL and exits 0. No spawn context is mutated. The flip to
enforcing mode requires ROLLOUT_GATE_PASS from
`/harness:swe-pruner-rollout-gate` (DEFERRED).

## Eval Results

- `eval_pass_rate`: 1.00 (all 121 tests passing at baseline commit)
- `eval_suite`: swe-pruner-unit-integration (tests/test_swe_pruner_*.py + tests/hooks/test_swe_pruner_hook_integration.py)
- `eval_n`: 121 tests

## Regression Anchor

Any future change to `hooks/_lib/swe_pruner.py` or
`hooks/pre-agent-swe-pruner.sh` MUST maintain `eval_pass_rate >= 1.00`
on the full `eval_suite`. A drop in pass rate is a regression requiring
investigation before merge.
