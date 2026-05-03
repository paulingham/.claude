---
task_id: wave3-structural-cleanup
phase: intake
classification: refactor
task_class: refactor
critical: false
bestofn: false
multi_repo: false
budget: 11
scope: 3
ambiguity: 1
context_pressure: 3
novelty: 1
coordination: 3
timestamp: 2026-05-03T21:43:46Z
designated_branch: claude/extract-rules-invariants-je52c
---

## Summary

Wave 3 — Structural cleanup of the harness. 13 atomic tasks across 5 themes
(C9 two-tier rules, C11 orchestrator/rules split, C12 engineering-protocol
split, C1 skill template + audit, C3 verdict catalog + audit, C5 advisor
frontmatter consistency, C7 fix-engineer agent).

## Routing Decision

Budget=11 → multi-session, must decompose. The 13 tasks are pre-planned with
clear ACs, which matches the `/batch-pipeline` pattern (skips Plan + Plan
Validation, preserves state tracking + Review + Reflect).

## Scope Conflict (FLAGGED)

The designated branch is `claude/extract-rules-invariants-je52c` — the name
maps specifically to C12.1 (extract engineering invariants from
engineering-protocol.md), not the full Wave 3. Shipping all 13 tasks on one
branch would produce an oversized PR that conflicts with the branch's
documented scope, and several themes (C9, C11) overlap C12 in the same files.

Recommended sequence:
1. This branch ships **C12.1 only** (engineering-invariants vs atdd-procedure split + CLAUDE.md auto-load update + skill references)
2. Subsequent branches per theme: `claude/two-tier-rules-{slug}`, `claude/orchestrator-rules-split-{slug}`, `claude/skill-template-{slug}`, `claude/verdict-catalog-{slug}`, `claude/advisor-frontmatter-{slug}`, `claude/fix-engineer-agent-{slug}`

C9 (two-tier rules) and C11 (orchestrator/rules split) both restructure the
same files C12 touches — landing C12 first lets them rebase against a stable
file shape rather than fighting merge conflicts.

## Dependencies Between Themes

- C9 depends on C12 (C9 carves invariants out of all rules/, C12 carves
  invariants out of engineering-protocol specifically)
- C11 depends on C9 (C11 moves orchestrator-only content out of files that
  C9 has already split into core/detail)
- C1, C3, C5, C7 are independent of C9/C11/C12

So the natural sequence is C12 → C9 → C11, with C1/C3/C5/C7 in any order
(parallelisable).

## Pre-flight

- CLAUDE.md present ✓
- No in-progress pipelines ✓
- Working tree clean ✓
- On designated branch `claude/extract-rules-invariants-je52c` ✓
