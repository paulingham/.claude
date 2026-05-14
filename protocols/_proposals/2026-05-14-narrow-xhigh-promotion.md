# Proposal: Narrow Unconditional xhigh Promotion to `critical OR budget>=7`

**Status:** PROPOSED (2026-05-14)
**Owner:** orchestrator-derived recommendation from cost forensics
**Implementation track:** requires `/pipeline` run (touches hooks, snapshot test, CLAUDE.md prose)

---

## Problem

Three production prompts consumed ~18% of a Claude Max 20x weekly allowance. Forensic decomposition (see § Burn Surface below) attributes the bulk of that spend to two compounding factors:

1. **Four roles run `effort=xhigh` unconditionally** — `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` (CLAUDE.md:45, `protocols/thinking-defaults.md` rule 3a lines 57–60). xhigh is the costliest reasoning tier and it fires on every spawn regardless of task stakes.
2. **A typical Critical pipeline emits ~18 Agent spawns**, of which 4–6 are at xhigh. Stack a PDR-RTV Build variant on top (5.5×–7.5× Build cost multiplier, fires on `budget>=9 OR critical`) and a single Critical pipeline routinely emits ~25–40 Opus-xhigh spawns.

The May 2026 postmortem note in CLAUDE.md:47 justified the unconditional promotion by arguing adaptive thinking *removed the cost gate*. That conclusion is partially correct (Opus 4.7 budget allocation is adaptive per spawn) but it does **not** make xhigh free — adaptive thinking sets the *budget ceiling* dynamically; the **floor** still scales with `effort`. xhigh produces meaningfully more thinking tokens per spawn than `high`, and thinking tokens are billed as output tokens.

## Proposed Change

Move `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` from the unconditional xhigh roster onto the same gate that already governs `security-engineer`:

```
xhigh trigger: critical=true OR budget>=7
default:       high
```

`architect` retains a slightly tighter floor (`critical=true OR budget>=6`) because Plan-phase under-reasoning has the highest blast radius — a bad plan compounds through every downstream phase. Best-of-N candidates keep their existing `budget>=7` gate.

| Role | Today | Proposed |
|------|-------|----------|
| `architect` | xhigh always | `critical OR budget>=6` → xhigh, else `high` |
| `software-engineer` | xhigh always | `critical OR budget>=7` → xhigh, else `high` |
| `frontend-engineer` | xhigh always | `critical OR budget>=7` → xhigh, else `high` |
| `infrastructure-engineer` | xhigh always | `critical OR budget>=7` → xhigh, else `high` |
| `security-engineer` | `critical AND budget>=7` → xhigh | unchanged |
| Best-of-N candidates | `budget>=7` → xhigh | unchanged |

## Expected Saving

Conservative estimate, holding pipeline shape constant:

- Routine (budget 3–5) pipelines: ~30–45% reduction in *output* token spend on Build/Plan phases, where thinking-token volume dominates.
- Aggregate weekly: ~20–30% reduction in tokens billed against the Max plan, assuming the user's pipeline mix is the typical mid-budget Build-heavy workload r/ClaudeAI users report (substack.com aicodingdaily 2026-05).
- Critical work is untouched — the gate still promotes xhigh when it matters.

## Why this is safe

1. **`security-engineer` already runs this exact gate.** The Apr 23 2026 promotion-on-trigger data referenced in CLAUDE.md:47 showed lift concentrated in stakes-bearing work, not routine implementation. `critical OR budget>=7` IS the operational definition of "stakes-bearing".
2. **The fix-engineer role already defaults to `high`** (CLAUDE.md:45) and reportedly performs well on Opus 4.7. It is on the same reasoning floor this proposal moves the four build roles to.
3. **Reversible per-session** via `CLAUDE_THINKING_EFFORT=xhigh` or `CLAUDE_EFFORT=xhigh` if a session needs the old behaviour. No state migration required.
4. **Two snapshot tests pin the change in `hooks/_lib/thinking_role.py`** — drift between docs and code surfaces immediately in CI, so partial implementation is caught.

## Implementation Checklist (for `/pipeline` run)

1. `hooks/_lib/thinking_role.py` — remove the four roles from `_PROMOTE_TO_XHIGH` frozenset; add gated promotion logic mirroring `security-engineer`.
2. `tests/test_thinking_defaults.py` — update `PromoteToXhighListMatchesAgentFrontmatter` snapshot; add new test cases for `critical=true` and `budget>=7` triggers per role.
3. `CLAUDE.md` § Thinking Defaults — replace "unconditional" prose at line 45 and the postmortem at line 47 with the new rule and rationale (cite this proposal).
4. `protocols/thinking-defaults.md` rule 3a (lines 56–69) — replace four unconditional bullets with one gated bullet; update Role Defaults Summary table (lines 71–86).
5. `agents/architect.md`, `agents/software-engineer.md`, `agents/frontend-engineer.md`, `agents/infrastructure-engineer.md` frontmatter — verify `default_effort` field matches the new policy if it exists.
6. `eval/baselines/{latest}-opus-4-7.md` — re-run baseline to confirm the 80% claim survives the downgrade (CLAUDE.md:13). If quality drops, the gate threshold widens (e.g. `budget>=5` instead of `>=7`).
7. Open one observation file post-merge to validate empirically (target: 25% weekly token reduction without quality regression on the next 10 mid-budget pipelines).

## Burn Surface (forensic detail)

Per-pipeline spawn count, Critical task, standard dispatch:

| Phase | Spawns | At xhigh today | At xhigh proposed |
|-------|--------|----------------|-------------------|
| Plan (architect + 3 recon) | 4 | 4 | 1 (architect on critical=true) |
| Plan Validation (heavy) | 2 | 1 (sw-eng) | 1 (sw-eng on critical=true) |
| Build (standard) | 1 | 1 (sw-eng or fe-eng) | 1 (on critical=true) |
| Code Review (inline) | 1 | 0 | 0 |
| Security Review | 1 | 1 (security on `critical AND budget>=7`) | unchanged |
| Final Gate 5-way + extra critic personas | 7 | 0 | 0 |
| Ship + Deploy | 2 | 0 | 0 |
| **Total xhigh spawns per Critical pipeline** | **18** | **~6** | **~3** |

Mid-budget (budget 4) pipelines see the largest delta: today every Build/Plan spawn is xhigh; proposed it drops to `high`. PDR-RTV scenarios get a compounding saving — 8 PDR-RTV build candidates × `high` instead of `xhigh` is a much steeper reduction than the same N spawns at `xhigh`.

## Counter-arguments considered

- **"xhigh quality on routine Build is measurably better."** Possibly true; the user-visible metric is `eval/baselines/{latest}-opus-4-7.md` (CLAUDE.md:13). Step 6 of the implementation checklist re-runs the baseline before flip — if quality regresses, the gate threshold widens. The baseline is the regression guard.
- **"`high` may not allocate enough adaptive-thinking budget for complex Build slices."** Adaptive thinking is per-spawn; the API allocates more budget for harder problems within the `effort` envelope. `high` is the floor `code-reviewer` and `qa-engineer` use today on the same Opus 4.7 model — both produce quality work. A `critical=true` pipeline still promotes to `xhigh`.
- **"This re-introduces the cost gate the May 2026 policy explicitly removed."** Yes, deliberately. The removal was premature — it assumed adaptive thinking would silently absorb the cost, but the empirical 18%-on-3-prompts datapoint shows the assumption broke. The proposal preserves the high-stakes promotion path while restoring proportionality.

## Rollback

Revert `_PROMOTE_TO_XHIGH` frozenset to its current four-role membership; restore CLAUDE.md prose. Snapshot test will guide the rollback.

---

**Linked PR for the spec rewrite track:** none yet — this proposal precedes implementation. Once approved, dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md exactly as specified. Budget: 6. Critical: false."
