---
id: sandbox-verify-seed
confidence: 0.5
roles:
  - sandbox-verify-engineer
  - qa-engineer
domain: testing
---

## Pattern

Three operating principles for the sandbox-verify validator (seed at confidence 0.5; refined as observation data accrues):

1. **The worktree pass set IS the contract.** Sandbox-verify exists to detect *divergence* between the worktree's test outcomes and the sandbox's test outcomes. If a test passes in the worktree but fails in the sandbox (or vice versa), that delta is the signal — never paper over it by retrying until the sets match. The diverging test name is more valuable than the bare verdict.
2. **`SANDBOX_SKIPPED` with a reason is information, not failure.** Missing `E2B_API_KEY`, sandbox provisioning timeout, cost-cap exceeded — these emit `SANDBOX_SKIPPED` with the reason enumerated. The pipeline advances; the reason is captured in the per-skip JSONL log for forensics. Treating SKIP as failure converts an info verdict into a build break and removes the gate's degraded-mode operating envelope.
3. **Read-only against the worktree.** The agent's `tools:` allowlist is `[Read, Grep, Glob, Bash]` deliberately — no Write/Edit/MultiEdit. The sandbox runs in a separate environment; the worktree is the source of truth and must not be mutated by the verify step. If a future story needs to mutate the worktree (it should not), it requires a new role, not a tools-list expansion.

## Why

The validator's value depends on it being a *neutral comparator* between two test runs (worktree-local and sandbox-remote). Each principle preserves a property the role needs to keep:

- Principle 1 keeps the role honest about its signal: divergence is what we measure, not eventual agreement.
- Principle 2 keeps the role usable in CI environments without E2B credentials and in cost-bounded operating modes — Story 3 will add `cost-cap-exceeded` to the reason enum, and Story 4 will surface skip rates in forensics. SKIP is a first-class outcome, not a fallback.
- Principle 3 keeps the role from acquiring write capabilities for "convenience" reasons that would let it mask real failures by editing the worktree mid-run.

## How to Apply

- When the diff helper reports `diverging_tests: [<names>]`, surface the verdict `SANDBOX_FAILED` with the enumerated list — do NOT retry the sandbox run hoping for convergence.
- When `E2B_API_KEY` is missing, emit `SANDBOX_SKIPPED` with reason `no-e2b-token` and append a JSONL line to `metrics/{session-id}/sandbox-verify-skips.jsonl` — Story 3 extends the enum to include `cost-cap-exceeded` and `e2b-provision-failed`; this seed instinct refines as those code paths land.
- When tempted to add Write/Edit to the agent's tools list "just to fix a build artifact in-line", STOP — open a new pipeline with a different role. The read-only constraint is the property; widening tools collapses the role.

## When NOT to Apply

- Pipelines that do not depend on Build-phase test outcomes (e.g. docs-only changes, infra-scaffolding) — sandbox-verify is gated by Build emission; the principles do not bind.
- During Story 2's Build-phase integration, when the parser shape and test-runner discovery are still in flight — principles 1 and 3 hold; principle 2's reason enum will gain entries as Stories 2/3 land.

## Source

Seed instinct authored alongside `agents/sandbox-verify-engineer.md` and `skills/sandbox-verify/SKILL.md` at confidence 0.5. Refined as observation data accrues — recurring `SANDBOX_FAILED` patterns will lift confidence and identify specific divergence classes (timing-sensitive tests, environment-dependent fixtures); recurring `SANDBOX_SKIPPED(cost-cap-exceeded)` after Story 3 lands will inform cost-cap defaults.
