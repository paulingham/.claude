---
name: vlm-critic
description: "Final-Gate teammate procedure for the vlm-critic agent. Reads the named PNG pair from `index.json.routes[*].visual_regression.{baseline_path, current_path}` plus `plan.md`, emits per-route `vlm_verdict ∈ {PASS, FAIL}` + `vlm_summary` back into index.json, and returns agent verdict `VISUAL_DIFF_PASS` (all routes PASS) or `VISUAL_DIFF_FAIL` (any route FAIL). Read scope is enforced by `hooks/vlm-critic-read-guard.sh` — `src/`, `lib/`, `app/` are blocked at the hook layer."
verdict: VISUAL_DIFF_PASS|VISUAL_DIFF_FAIL
phase: final-gate
dispatch: subagent
agent: vlm-critic
---

# Vlm Critic

## What This Skill Does

Adds a **semantic-diff Final Gate teammate** that compares baseline+current screenshot pairs and writes a per-route `vlm_verdict` (PASS|FAIL) + ≤50-word `vlm_summary` into `pipeline-state/{task-id}/design-qc/index.json`. The pixel-diff producer (design-qc Step 6 via `hooks/_lib/visual_diff.js`) and the vlm-critic semantic-diff producer (this skill) BOTH feed product-reviewer; product-reviewer gates APPROVE on `pixel_diff_ratio < threshold AND vlm_verdict == PASS` for every route.

`hooks/vlm-critic-read-guard.sh` enforces the constraint by exiting 2 on any read attempt outside the vlm-critic-allow-paths allowlist (PNG pairs, plan.md, the index.json itself). The hook is a structural clone of `hooks/spec-blind-read-guard.sh` with renamed prefix `_vlm_critic_*` — soak-safe per the 2026-06-09 spec-blind V2 freeze (plan § 8).

## When to Invoke

- Final Gate phase, in parallel with `/harness:verify`, `/harness:qa-test-strategy`, `/harness:product-acceptance`, `/harness:patch-critique`, and `/harness:spec-blind-validate`.
- Only when design-qc emitted `SCREENSHOTS_CAPTURED` AND `index.json.visual_regression.captured == true` for the current run.
- After `/harness:code-review` and `/harness:security-review` both APPROVED (Build phase complete).

If `index.json.visual_regression.captured == false` (e.g. baseline build on `main` failed — see plan § 7 row 1), this skill is NOT invoked; design-qc falls back to text-only product-review per `agents/product-reviewer.md:40`.

## Inputs

The orchestrator hands the spawned agent these inputs in the prompt:

| Input | Source |
|-------|--------|
| AC plan | `pipeline-state/{task-id}/plan.md` (verbatim) |
| Index.json path | `pipeline-state/{task-id}/design-qc/index.json` (input + Write target) |
| Route set | `index.json.routes[*]` — every route with `visual_regression.{baseline_path, current_path}` |

The agent is NOT given `git diff main...HEAD` — implementation source is OUT of scope by design.

## Allowed Inputs (convention-based — vlm-critic's read allowlist)

The path-allowlist is established by `hooks/_lib/vlm-critic-allow-paths.{sh,txt}` and consumed by the read-guard.

| Glob (ERE) | Purpose |
|---|---|
| `pipeline-state/.+/visual-baselines/[^/]+\.png` | Baseline screenshots (against `main`) — primary input |
| `.*/\.claude/screenshots/[^/]+\.png` | Current-branch screenshots — comparison input |
| `pipeline-state/.+/design-qc/index\.json` | Per-route inputs + Write target |
| `pipeline-state/.+/plan\.md` | The AC plan (informs in-scope/out-of-scope visible changes) |

**Denied (concrete examples)**: `src/**`, `lib/**`, `app/**`, `internal/**`, `cmd/**`, `pkg/**`, `bin/**`, `dist/**`, `build/**`, `node_modules/**`, `vendor/**`. Default-deny.

## Tool Surface (SE-2 pinned)

The vlm-critic agent declares `tools: [Read, Write]` exactly with `disallowedTools: [Bash, Edit, MultiEdit, Agent, Skill, Grep, Glob]`. The narrower surface (vs spec-blind-validator's 5-tool surface) reflects that vlm-critic operates on a **closed file set** named by the index.json producer — no discovery (Grep/Glob) and no shell side-effects (Bash) required. The single side-effect is the Write back to index.json. See plan § 2 SE-2 row for full rationale.

## Output (Write target — scoped to index.json)

For every route in `index.json.routes[*]`, write:

```json
{
  "route": "/dashboard",
  "visual_regression": {
    "baseline_path": "pipeline-state/<task-id>/visual-baselines/dashboard-desktop.png",
    "current_path": ".claude/screenshots/dashboard-desktop.png",
    "pixel_diff_ratio": 0.012,            // already populated by design-qc Step 6
    "vlm_verdict": "PASS",                // YOU write this
    "vlm_summary": "No semantic regression. Dashboard cards and CTA preserved across both viewports."  // YOU write this
  }
}
```

`vlm_summary` MUST be ≤50 words and cite the route by name + the named delta (or "no semantic regression" when PASS).

## Verdict Logic (aggregate)

- All routes PASS → return `VISUAL_DIFF_PASS`.
- Any route FAIL → return `VISUAL_DIFF_FAIL`.

The aggregate verdict matches the per-route verdicts deterministically:

```
if every route in routes[*] has vlm_verdict == "PASS":
    return VISUAL_DIFF_PASS
else:
    return VISUAL_DIFF_FAIL
```

## Determinism / Temperature

Vlm-critic operates at **temperature 0** with a strict structured-output template:

```
vlm_verdict: PASS|FAIL
vlm_summary: <≤50 word English summary>
```

This is the contract that defends against flaky verdict-flipping across runs (plan § 7 row 4). The contract is asserted by the Tier 2 integration test (`tests/integration/test_design_qc_visual_regression_e2e.py`) which runs vlm-critic twice on the same fixture pair and asserts equal verdicts.

## Escape Hatch — `CLAUDE_DISABLE_VLM_CRITIC=1` (PR-3 pinned)

If `CLAUDE_DISABLE_VLM_CRITIC=1` is set in the environment when this agent spawns, the procedure short-circuits **BEFORE any multimodal Read** of the PNG pairs:

1. Iterate over every route in `index.json.routes[*]`.
2. Write `routes[i].visual_regression.vlm_verdict = "PASS"`.
3. Write `routes[i].visual_regression.vlm_summary = "<route>: disabled-by-env"` (the literal token `disabled-by-env` MUST appear in every route's summary).
4. Return verdict `VISUAL_DIFF_PASS`.

**No multimodal Read is issued.** A Tier 1 unit test (`tests/test_vlm_critic.py::test_vlm_critic_disabled_via_env_short_circuits_to_PASS`) asserts the call count on the Read-multimodal stub equals 0 when the env var is set.

**Why the hatch exists.** Vision-language verdicts can be non-deterministic across runs even at temperature 0 (model floor effects). If a project starts hitting flaky verdicts (`VISUAL_DIFF_FAIL → PASS → FAIL` on identical inputs), the hatch is the one-line revert path that unblocks the pipeline while the verdict logic is fixed in a follow-up. The hatch is intentionally documented + pinned by a contract test so future "simplifications" cannot quietly remove it.

## Read-Guard Enforcement Posture

`hooks/vlm-critic-read-guard.sh` ships as **full enforcement (exit 2 on block)**, NOT Path-B advisory. Rationale (plan § 4):

`hooks/spec-blind-read-guard.sh` is full enforcement today. The Path-B advisory pattern applies to PreToolUse Agent hooks where `thinking` / `modified_tool_input` / `allowed_tools` are not yet exposed by the Agent input schema. Read-guard hooks operate on the Read tool's `tool_input.file_path`, which IS exposed today (every existing read-guard hook reads it). The schema-exposure problem does not apply to read-guard hooks.

JSONL violation logs at `metrics/$SESSION/vlm-critic-violations.jsonl` provide forensic visibility identical to spec-blind's `spec-blind-violations.jsonl`.

## Process

> **Subagent-type resolution (SEC-MED-2).** The read-guard resolves `subagent_type` via this fallback chain: (1) the `.subagent_type` top-level field on the PreToolUse JSON envelope, (2) the `CLAUDE_SUBAGENT_TYPE` environment variable. The orchestrator MUST set `CLAUDE_SUBAGENT_TYPE=vlm-critic` in the spawn shell when dispatching this agent so the guard still fires even if the harness omits the JSON field. Mirrors the precedent at `hooks/cost-feed.sh:33`.

1. **Escape-hatch check (BEFORE any Read).** If `CLAUDE_DISABLE_VLM_CRITIC=1` is set, jump to § Escape Hatch above and short-circuit. No PNG reads are issued.

2. **Read inputs.** Read `pipeline-state/{task-id}/design-qc/index.json` and `pipeline-state/{task-id}/plan.md`. The index.json names every route; the plan informs whether a visible delta is in-scope.

3. **Per-route comparison.** For every route in `index.json.routes[*]`:
   - Read the baseline PNG at `route.visual_regression.baseline_path` (multimodal Read).
   - Read the current PNG at `route.visual_regression.current_path` (multimodal Read).
   - At temperature 0, decide `vlm_verdict ∈ {PASS, FAIL}` and produce a ≤50-word `vlm_summary` citing the route + the named delta.
   - Write both fields back to the route's entry in index.json.

4. **Aggregate + return.** If every route is PASS → emit `VISUAL_DIFF_PASS`. Otherwise emit `VISUAL_DIFF_FAIL` and name the failing route(s) in the agent's stdout.

5. **No additional side-effects.** No Bash, no Grep, no Glob, no Edit/MultiEdit, no Agent/Skill delegation. The only Write is into index.json under each route's `visual_regression` block.

## Anti-Patterns

- Reading `src/component.tsx` to "understand the button" → BLOCKED at the hook layer; logged to `vlm-critic-violations.jsonl`.
- Emitting "unsure" or empty `vlm_verdict` → BLOCKED by structured-output template (must be PASS or FAIL).
- Emitting `vlm_summary` >50 words → soft-warn in product-reviewer; treat as a contract drift; correct in fix-engineer round.
- Bypassing the escape-hatch contract (e.g. issuing PNG Reads when `CLAUDE_DISABLE_VLM_CRITIC=1`) → caught by Tier 1 unit test mock assertion.

## Verdicts

- **VISUAL_DIFF_PASS** — every route PASS. Product-reviewer reads the same index.json and continues to APPROVE-gate logic.
- **VISUAL_DIFF_FAIL** — any route FAIL. Spawn fix-engineer per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule (code-fix-only — fix-engineer MUST NOT mutate ACs).

See `protocols/verdict-catalog.md` for the agent-emitted footnote.

## No-Diff Control Invariant

An identical baseline/current PNG pair produces `pixel_diff_ratio == 0.0`. The vlm-critic **MUST** assess such a pair as `vlm_verdict PASS`, contributing to the aggregate `VISUAL_DIFF_PASS` verdict.

**Failure semantics:** If vlm-critic emits `VISUAL_DIFF_FAIL` on a no-diff control pair (pixel_diff_ratio == 0.0), this is a **hallucinated regression** and is a **vlm-critic defect**, not a product defect. The product has not changed; the agent has incorrectly assessed an identical pair as different.

**Opt-in live guard:** Set `CLAUDE_VLM_LIVE_CONTROL=1` to run `tests/integration/test_vlm_critic_live_control.py`, which dispatches the vlm-critic procedure via `claude -p` headless against a staged identical PNG pair and asserts `VISUAL_DIFF_PASS` in stdout. This test is skipped by default in CI (billable model call).

**Tier 1 doc-contract test:** `tests/test_vlm_critic.py::NoDiffControlInvariant` pins this invariant by asserting the presence of the key terms in this SKILL.md section.

## Phase Output

```
Verdict: VISUAL_DIFF_PASS / VISUAL_DIFF_FAIL
Routes evaluated: <n>
Routes failed: <names + summaries>
Index.json updated: pipeline-state/<task-id>/design-qc/index.json
```
