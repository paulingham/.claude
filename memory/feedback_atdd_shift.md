---
name: ATDD discipline shift (wave4-R)
description: Replaced incremental per-behaviour TDD with batched ATDD plus mutation gate; tdd-guard hook moved from Write/Edit to PR-creation boundary.
type: feedback
date: 2026-04-28
task_id: wave4-R
---

## What Changed

The harness shifted from **incremental per-behaviour TDD** (one test, one impl, one refactor, repeat) to **Acceptance-Test-Driven Development (ATDD)** with a single batched RED-GREEN-REFACTOR cycle plus a quantitative mutation gate per slice.

- `protocols/atdd-procedure.md` (split out of `rules/engineering-protocol.md` in 2026-05) defines the ATDD Protocol that replaced the old "Incremental TDD Protocol". Three test invocations per slice (batched RED, post-implementation GREEN, post-refactor GREEN) plus one mutation report. Same mandatory Iron Laws, different cadence. Engineering invariants (shape, naming, security baseline, testing standards) live in `protocols/engineering-invariants.md`.
- `skills/build-implementation/SKILL.md` Step 1 now reads the architect's per-AC failing-test stub list and halts if any AC has no stub. Step 2 implements the batched ATDD cycle.
- `hooks/tdd-guard.sh` rewired from PreToolUse Write/Edit to PreToolUse Bash gate. Triggers only on `gh pr create` / `gh pr ready`. Blocks PR creation when the diff against the base branch contains source changes with no test changes. Helper logic in `hooks/_lib/tdd-guard-pr.sh` (50 lines, self-contained).
- `skills/verify/SKILL.md` Tier 3 (mutation testing) is now a HARD GATE at >= 70% kill rate on changed lines. Below threshold = UNVERIFIED. The manual fallback is approved as gate-passing methodology, but the threshold still applies.
- `skills/story-writing/SKILL.md` adds a "Failing Test Stubs (per AC)" step; `agents/architect.md` adds the same to its Output Format.
- `agents/qa-engineer.md` preamble rewritten to a three-phase model: Plan-phase stub authoring, Verify-phase tier execution with mutation gate, Test-phase gap-fill.
- `skills/bug-fix/SKILL.md` retains per-behaviour RED-GREEN-REFACTOR (the documented exception to ATDD's batched cycle), with an explicit RED-first iron law added.

## Trade-off Accepted

ATDD is closer to Kent Beck's original TDD intent: test the *acceptance criterion*, not synthetic micro-behaviours. Batched RED reduces three test invocations per AC down to three per slice — material wall-clock saving on multi-AC slices, and the audit trail still proves both the absence of behaviour (batched RED) and the presence of behaviour (post-refactor GREEN).

The mutation gate fixes the well-known weakness of "tests pass" as a quality signal. A green suite with low mutation kill rate means the tests are not exercising the changed lines. Promoting Tier 3 to a hard gate makes that signal a deal-breaker, not a soft warning.

The hook move from Write/Edit to PR-creation is structural: the old hook fired thousands of times per build (every Write/Edit) and produced friction inside the cycle. The PR boundary is the natural enforcement point — the diff is final, the contract is testable, and the engineer has the full slice in front of them, not one test at a time.

## Per-Behaviour TDD Exceptions

The batched cycle does NOT apply to:
- **Bug fixes** — the repro test IS the contract; per-behaviour TDD via `skills/bug-fix/SKILL.md`.
- **Complex algorithmic logic** — parsers, state machines, financial maths.
- **Security-sensitive code** — auth, crypto, ACL checks; each rule gets its own RED step.

For these, the old per-behaviour RED-GREEN-REFACTOR remains the contract.

## Conditions to Revisit

- Mutation tooling becomes prohibitively expensive on a project's scale → consider raising the gate to `verify-only` rather than `build-only` so the cost falls on the verify phase budget, not every build.
- Code-reviewer reports indicate engineers are gaming the batched RED (writing tests that all pass trivially) → tighten the architect stub contract: require the assertion intent to be specific enough that the build agent cannot satisfy it via a stub.
- A regression appears where bug-fix work bypasses the per-behaviour exception → add a hook on `skills/bug-fix/` invocations that asserts the RED output was captured before any source edit.
