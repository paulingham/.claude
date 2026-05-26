# Proposal: Promote Effort / Model / Cache-Breakpoint Hooks From Advisory to Enforcing on Claude Code 2.3.0

**Status:** PROPOSED (2026-05-24)
**Owner:** orchestrator-derived recommendation from external research + cost forensics
**Implementation track:** requires `/pipeline` run (touches three hooks, snapshot tests, CLAUDE.md prose)

---

## Problem

Three of the harness's cost-control PreToolUse:Agent hooks are **resolved-but-not-enforced** — they compute the correct decision and write it to JSONL, then `exit 0` without changing the spawn:

| Hook | Resolver | Current behaviour | Flip surface |
|------|----------|-------------------|--------------|
| `hooks/pre-agent-thinking.sh` | `_lib/resolve-thinking.py` | `[[ "$DECISION" == "LOG" ]] \|\| exit 0` → log-injection only (line 33–35) | line 28–35 |
| `hooks/pre-agent-advisor.sh` | `_lib/advisor_resolver.py` | logs `advisor-dispatch.jsonl`, never blocks | tail (log-injection call) |
| `hooks/cache-breakpoint-injector.sh` | `_lib/resolve-cache-breakpoints.py` | `[[ "$DECISION" == "LOG" ]] \|\| exit 0` → log-injection only (line 30–32) | line 28–32 |

Every hook header and `CLAUDE.md` cites the same root cause: *"the Agent tool input schema does not currently expose `thinking` / `advisor` / `modified_tool_input`, so enforcement is deferred until Claude Code lands Path A support (v2.1.140)."*

**The deferral premise is now stale.** `version-pin` reads `2.3.0`. External release research (code.claude.com/docs/en/whats-new, ~Week 19, v2.1.13x) reports that Claude Code shipped:

- Subagent dispatch flags on the Agent tool: **`--effort`, `--model`, `--permission-mode`, `--plugin-dir`**.
- Hooks now see active effort via **`effort.level`** and **`$CLAUDE_EFFORT`** (the latter is already consumed by `resolve-thinking.py` rule 2a per `CLAUDE.md`).
- PostToolUse can replace tool output for all tools via `hookSpecificOutput.updatedToolOutput`.

If those flags are GA in 2.3.0, the orchestrator can pass the **resolved** effort and model on every Agent spawn, and the three resolvers stop being advisory. Today the consequence of the gap is concrete and expensive:

- **Narrow-xhigh-promotion (PR #124) does not bite.** The resolver computes `high` for a routine budget-4 Build, but nothing applies it — the spawn runs at whatever the model defaults to. The ~18%-on-3-prompts datapoint that motivated #124 is only *partially* mitigated because the gate is log-only.
- **The Sonnet-solo `code-reviewer` arm (`model_conditional`, budget < 6) does not bite.** Both arms run Opus today (audit confirmed). Every routine review pays Opus input+output rates when Sonnet was the resolved choice.
- **Cache breakpoints are not injected**, so the `rules-core-tail` anchor never lands and read-ratio sits below what multi-anchor caching would deliver (ProjectDiscovery measured ~70% with multi-anchor; harness target is 0.65).

## Proposed Change

1. **Verify the dispatch-flag surface on the pinned version** (`version-pin` = 2.3.0). Confirm `--effort` and `--model` are accepted on Agent spawns and that `effort.level` is present in the PreToolUse:Agent payload. This is the single gating fact for the whole proposal.
2. **If confirmed, flip the three hooks from log-only to enforcing**, one at a time, each behind its existing reversibility env var:
   - `pre-agent-thinking.sh` — on `DECISION == "ENFORCE"`, emit the resolved `effort` so the spawn runs at the gated tier. Keep `CLAUDE_DISABLE_THINKING_GATE=1` as the escape.
   - `pre-agent-advisor.sh` — emit the resolved executor/advisor model. Keep `CLAUDE_DISABLE_ADVISOR_GATE=1`.
   - `cache-breakpoint-injector.sh` — emit the resolved anchor breakpoints. Keep the existing disable path.
3. **Stage the rollout**: thinking gate first (largest, best-understood saving), measure 10 pipelines, then advisor, then cache breakpoints. Each flip is one PR-sized change.
4. **If NOT confirmed on 2.3.0**, the proposal closes with a documented negative result and a re-check trigger pinned to the next minor bump — no code change, but the stale "v2.1.140" deferral notes in the three hook headers and `CLAUDE.md` get corrected to "as of 2.3.0, pending `--effort`/`--model` GA confirmation" so the next reader doesn't re-derive this.

## Expected Saving

On a Max 20x plan the currency is **weekly token quota**, not API dollars. The enforced gates cut quota burn at three independent points:

- **Thinking enforcement**: routine (budget 3–6) Build/Plan spawns drop from the de-facto model default to gated `high`. Thinking tokens bill as output; this is the largest lever. The #124 proposal estimated ~20–30% weekly token reduction from this gate — *currently unrealised because it is log-only.*
- **Advisor/model enforcement**: every budget-<6 code-review moves Opus→Sonnet (≈40% cheaper per review, provisional).
- **Cache-breakpoint enforcement**: lifts read-ratio toward 0.70; cache reads bill at 0.1× input, so each recovered anchor hit is a ~90% saving on that segment.

Combined, this is plausibly the difference between the documented "3 prompts = 18% of weekly quota" and a materially lower burn — because it activates gating the harness *already designed and tested* but never turned on.

## Why this is safe

1. **No new logic.** The resolvers (`resolve-thinking.py`, `advisor_resolver.py`, `resolve-cache-breakpoints.py`) and their snapshot tests already exist and are exercised in CI. This flips an output path, not a decision.
2. **Per-hook reversibility is already wired** (`CLAUDE_DISABLE_THINKING_GATE`, `CLAUDE_DISABLE_ADVISOR_GATE`, cache disable). Any misclassification is a one-env-var rollback, no redeploy.
3. **Staged, measured rollout** — one hook at a time, 10-pipeline observation window between flips, with `eval/baselines/{latest}-opus-4-7.md` as the quality regression guard (same guard #124 used).
4. **Gating only ever lowers cost on routine work**; `critical=true OR budget>=7` still promotes to xhigh/Opus where it matters, so high-stakes quality is untouched.

## Implementation Checklist (for `/pipeline` run)

1. **Probe step (blocking gate for the rest):** in a throwaway session on 2.3.0, dispatch an Agent with `--effort high --model sonnet` and inspect the PreToolUse:Agent payload for `effort.level`. Record the result in this proposal's § Findings before proceeding. (`hooks/probe-modified-tool-input.sh` already exists for exactly this kind of schema probe — extend or mirror it.)
2. `hooks/pre-agent-thinking.sh` — add an `ENFORCE` branch that emits resolved effort; gate it on a feature flag (`CLAUDE_THINKING_ENFORCE=1` initially) so the flip is itself reversible during soak.
3. `hooks/_lib/resolve-thinking.py` — emit `ENFORCE` instead of `LOG` when the schema probe passed (read a capability marker written by step 1, do not hardcode the version).
4. Repeat 2–3 for `pre-agent-advisor.sh` / `advisor_resolver.py` and `cache-breakpoint-injector.sh` / `resolve-cache-breakpoints.py`, each as a separate commit.
5. Update the three hook headers and the `CLAUDE.md` § Thinking Defaults / § Advisor-Mode / § Cost Discipline notes to reflect enforcing status (remove "advisory/log-only at v2.1.140").
6. `tests/` — add an enforcement-path test per hook asserting the resolved value is emitted on a synthetic ENFORCE decision.
7. Open one observation file per flip; target ≥15% weekly token reduction across the next 10 mid-budget pipelines with no `eval/baselines` regression.

## Counter-arguments considered

- **"The schema still might not expose these on 2.3.0."** That is exactly what step 1 (probe) settles before any code changes. Negative result → documented re-check, zero risk.
- **"Enforcing effort could starve a hard Build slice of reasoning budget."** Adaptive thinking allocates within the `effort` envelope per-spawn; `high` is the floor `code-reviewer`/`qa-engineer` already run on Opus 4.7 with good results, and `critical OR budget>=7` still promotes to xhigh.
- **"Sonnet reviews might miss findings Opus catches."** The advisor flip is gated to budget < 6 (the `model_conditional` arm the harness already defines); the soak window + baseline guard catch any regression, and `CLAUDE_DISABLE_ADVISOR_GATE=1` reverts instantly.

## Rollback

Set the relevant `CLAUDE_*_ENFORCE` flag to 0 (or the existing `CLAUDE_DISABLE_*` escape to 1). Hooks revert to log-only. No state migration.

---

**Linked PR for the spec rewrite track:** this proposal. Once the probe confirms the schema, dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-24-enforce-effort-model-gates.md, thinking-gate flip ONLY (step 1–3, 5–7). Budget: 7. Critical: true." Then repeat per remaining hook.
