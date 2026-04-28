---
name: thinking-defaults xhigh boundary reviewed (wave4-R)
description: Decision to NOT extend xhigh trigger to code-reviewer or qa-engineer/verifier. Boundary stays where it is.
type: feedback
date: 2026-04-28
task_id: wave4-R
---

## Decision

Reviewers (`code-reviewer`) and verifier (qa-engineer running `/verify`) do NOT escalate to `effort=xhigh` when `critical=true OR budget>=7`. They stay at `effort=high` regardless of task class.

## Why

- Detection roles, not design roles. xhigh's marginal value is in exploring an alternative space (architecture, threat modeling). Review and verify are bounded against a completed artifact — fewer alternatives to explore, more pattern-matching against known defect classes.
- The xhigh Leakage Boundary section in `rules/thinking-defaults.md` (lines 92–100) explicitly excludes these roles. Test suite #13/#14/#15/#20 in `tests/test_thinking_defaults.py` locks the exclusion as a regression guard.
- Recovery cost asymmetry: a missed review finding triggers an in-cycle fix-engineer cycle (bounded, cheap). A missed design decision rebuilds the system (unbounded, expensive). xhigh budget should track recovery cost, not just task criticality.
- Cost: every promotion to xhigh roughly doubles per-call token spend. Two roles × every critical-or-budget>=7 pipeline = a measurable budget hit for marginal quality lift.

## Conditions to Revisit

- A documented case where a reviewer or verifier missed a regression that xhigh effort would plausibly have caught (concrete file:line, replayable). Pull a sample of the last 20 review CHANGES_REQUESTED rounds — if >=3 of them are "reviewer missed it on round 1, caught on round 2", reconsider.
- If `eval/baselines/{latest}-advisor-baseline.md` shows the Sonnet-executor + Opus-advisor pairing has measurably lower verdict-agreement than Opus-solo on critical-budget pipelines, the cheaper fix is restoring Opus-solo for those pipelines (existing override `CLAUDE_REVIEW_ADVISOR_DISABLED=1`), not adding xhigh.
- A future Opus version where xhigh becomes materially cheaper (<= 1.5x high) — the cost objection weakens and broader application becomes defensible.
