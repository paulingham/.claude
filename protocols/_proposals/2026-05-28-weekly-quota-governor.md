# Proposal: Weekly-Quota-Aware Dispatch Governor (closed-loop cost control)

**Status:** PROPOSED (2026-05-28)
**Owner:** orchestrator-derived recommendation from external research (Claude Code `/usage` per-category attribution; `task-budgets` beta) + harness cost forensics
**Implementation track:** requires `/pipeline` run (touches `hooks/_lib/cost_estimator.py`, `skills/cost-report`, `statusline-command.sh`, `orchestrator/parallel-dispatch-details.md`, a new `hooks/_lib/quota_governor.py`, `protocols/cost-discipline.md`)

---

## Problem

The harness measures cost **after the fact** and never acts on it. `hooks/cost-feed.sh` writes per-spawn tokens to `metrics/{session}/cache.jsonl`; `/cost-report` and `/cache-audit` are **manual, post-hoc** skills; `statusline-command.sh` renders only `memoryUsagePercent`. Nothing watches **cumulative weekly burn** against the Max-20x quota, and nothing **downshifts dispatch when the week is running out**. This is the direct cause of the reported failure mode: *"3 prompts on May 11 = 18% of a weekly Max 20x plan,"* i.e. ~17 such prompts drains a week with no warning and no automatic throttle. A harness whose default dispatch fans out to 5 Final-Gate agents + 2 reviewers + 2–3 Best-of-N candidates, each on Opus, is structurally exposed to quota exhaustion days early.

Two new Claude Code / API primitives (May 2026) make a closed loop cheap to build:

1. **`/usage` per-category cost breakdown** (Claude Code v2.1.149+) — native attribution of spend by subagent, skill, plugin, and per-MCP-server. Source: [Claude Code What's New](https://code.claude.com/docs/en/whats-new). This is the missing *input signal*: it tells us *which* spawns burn quota, not just that quota was burned.
2. **`task-budgets` beta** (`task-budgets-2026-03-13` header) — an advisory token budget across the whole agentic loop; the model sees a countdown and self-moderates. Distinct from `max_tokens` (hard cap). Min 20k. Source: [Opus 4.7 API docs](https://platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7). This is the missing *per-spawn throttle*.

## Proposed Change

Add a **read-mostly governor** that turns measured burn into a dispatch decision at two levels:

1. **Rolling-window burn ledger.** A new `hooks/_lib/quota_governor.py` aggregates the existing `metrics/*/cache.jsonl` + `cost_estimator.py` output into a **7-day rolling token total** and a `burn_fraction` against a single operator-set constant `WEEKLY_QUOTA_TOKENS` (lives once in `protocols/cost-discipline.md`, mirrors the `READ_RATIO_TARGET` single-source discipline). Where available, seed it from `/usage` per-category output rather than re-deriving.
2. **Three governor bands, each a *downshift*, never an upshift:**
   | Band | `burn_fraction` | Automatic action |
   |------|-----------------|------------------|
   | GREEN | < 0.60 | No change — full dispatch shape |
   | AMBER | 0.60–0.85 | Final Gate drops 5→3 agents on T4/T5; Best-of-N suppressed (falls back to single-candidate Build, emits `BoN_FALLBACK_TO_SINGLE`); review stays |
   | RED | > 0.85 | Above + executor model forced Opus→Sonnet on all `Tunable` roles; tier floor for fan-out raised (T5 dispatched as T4 shape); `critical=true` work still runs full but emits a loud quota warning |
3. **Per-spawn `task_budget` derived from tier/complexity** (the throttle): map the existing complexity budget → a `task_budget` token countdown passed on each Agent spawn (e.g. T4 ≈ 60k, T5 ≈ 120k, T6 ≈ 250k; tunable table in `protocols/cost-discipline.md`). This is additive and independent of the bands — it bounds per-spawn runaway even in GREEN.
4. **Statusline burn glyph** in `statusline-command.sh`: green/amber/red dot from the most recent ledger read (no extra API call — reads the same `cache.jsonl` tail). Always-visible early warning so the operator sees AMBER on Tuesday, not RED on Friday.
5. **Override + forensics.** `CLAUDE_QUOTA_GOVERNOR=off` disables all downshifts (escape hatch). Every band transition and every auto-downshift writes one JSONL line to `metrics/{session}/quota-governor.jsonl` for `/forensics` and `/learn`.

## Expected Saving

- The governor's value is **bounded, automatic spend control**: it caps the worst case (running dry mid-week) by trading dispatch *breadth* for *survival* exactly when quota is scarce. On the reported 18%-per-3-prompts profile, AMBER alone (Final Gate 5→3, BoN suppressed) removes ~4 Opus spawns from every heavy pipeline — a material fraction of per-pipeline burn — only on the pipelines run after 60% weekly consumption.
- `task_budget` per-spawn prevents the silent runaway spawn (the one that thinks for 200k tokens on a budget-4 task) regardless of band.
- Zero cost in GREEN — the common case is untouched.

## Why this is safe

1. **Downshift-only, never upshift.** The governor can only make dispatch *cheaper/narrower*; it never escalates, so it cannot increase spend or weaken a `critical` pipeline (critical work still runs full, just with a warning).
2. **Reuses existing telemetry** — `cache.jsonl`, `cost_estimator.py`, the `/usage` native breakdown. No new measurement surface, only aggregation + a decision.
3. **Single-source constants** (`WEEKLY_QUOTA_TOKENS`, band thresholds, `task_budget` table) in `protocols/cost-discipline.md`, same staged-flip governance as `READ_RATIO_TARGET`.
4. **One-env-var rollback** (`CLAUDE_QUOTA_GOVERNOR=off`).
5. **Quality guard:** band downshifts only ever touch `Tunable` roles and dispatch breadth, never the `architect`/`security-engineer` hard locks, never the ATDD/mutation/spec-blind gates.

## Implementation Checklist (for `/pipeline` run)

1. `protocols/cost-discipline.md` — add § Weekly Quota Governor: define `WEEKLY_QUOTA_TOKENS`, the three band thresholds, the tier→`task_budget` table, and the override env var, all as single-source constants.
2. `hooks/_lib/quota_governor.py` — aggregate `metrics/*/cache.jsonl` into a 7-day rolling total + `burn_fraction`; expose `band()` and `task_budget_for(tier)`; prefer `/usage` per-category seed where present. Pure function, unit-tested.
3. `orchestrator/parallel-dispatch-details.md` — document that the dispatcher reads `band()` before each phase and applies the AMBER/RED downshifts to Final Gate agent count, Best-of-N gating, and `Tunable` executor model; passes `task_budget_for(tier)` on every Agent spawn.
4. `statusline-command.sh` — add the burn glyph (green/amber/red) from the ledger tail; cheap, no API call.
5. `skills/cost-report/SKILL.md` — surface the current band + 7-day burn in the report header.
6. `tests/` — fixtures for each band boundary (0.59/0.60/0.85/0.86) asserting the correct downshift set; a `task_budget` mapping test per tier; a test that `critical=true` is never downshifted; an override-off test.
7. Open one observation after 10 pipelines comparing weekly burn-rate before/after, and how often AMBER/RED fired.

## Counter-arguments considered

- **"`WEEKLY_QUOTA_TOKENS` is unknown — Max 20x publishes no token number."** Calibrate it empirically: the operator sets it from observed `/usage` over one full week (the reported 18%-per-3-prompts datapoint is itself a calibration point). The constant is operator-tunable; a wrong value only shifts band timing, never breaks dispatch.
- **"Downshifting Final Gate weakens production-readiness."** AMBER drops Final Gate 5→3 only on T4/T5 (bug-fix / standard feature), keeps verify + patch-critique + spec-blind on T6, and never touches the ATDD/mutation gates. The trade is dispatch *breadth*, not the correctness floor.
- **"This duplicates the fan-out cap work (#154)."** #154 caps fan-out by *tier/budget* (a static rule). The governor caps by *remaining weekly quota* (a dynamic, time-varying signal). They compose: #154 sets the ceiling, the governor lowers it further when the week is running out.

## Rollback

Set `CLAUDE_QUOTA_GOVERNOR=off`; dispatch reverts to #154 static shape. `task_budget` emission is independently disablable. The ledger + glyph are read-only and harmless if left on.

---

**Linked PR for the spec track:** this proposal. Dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-28-weekly-quota-governor.md exactly as specified. Budget: 7. Critical: true."
