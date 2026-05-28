# Proposal: Unblock Effort/Model Enforcement via the Orchestrator-Flag Path (not hook mutation)

**Status:** PROPOSED (2026-05-28) — supersedes the blocking premise of `2026-05-24-enforce-effort-model-gates.md`
**Owner:** orchestrator-derived recommendation from external release research (Claude Code v2.1.139+ dispatch flags) + the RED probe at `pipeline-state/promote-advisory-hooks-enforcement/probe-result.md`
**Implementation track:** requires `/pipeline` run (touches `orchestrator/agent-orchestration.md`, `orchestrator/parallel-dispatch-details.md`, the three resolver call-sites, snapshot tests, `CLAUDE.md` prose)

---

## Problem

The harness's three cost-control hooks (`pre-agent-thinking.sh`, `pre-agent-advisor.sh`, `cache-breakpoint-injector.sh`) all **resolve the cheaper decision then `exit 0`** without applying it. The existing `enforce-effort-model-gates` proposal (#150) correctly identifies this as the largest unrealised quota saving — the resolver computes `high` for a routine Build, the Sonnet arm for a budget-<6 review — but **nothing applies it**, so every routine spawn pays whatever the model defaults to (audit confirms both code-reviewer arms run Opus today).

That proposal is **blocked on the wrong fact.** It assumes enforcement requires the hook to mutate `tool_input` via a `modified_tool_input` round-trip. The probe at `pipeline-state/promote-advisory-hooks-enforcement/probe-result.md` returned **RED at v2.1.141** for exactly that round-trip, and it was never safely re-runnable from inside a subagent.

**External release research changes the picture.** The mutation round-trip is *not the only enforcement path* — and arguably not the right one:

- Claude Code shipped **`--effort` and `--model` as dispatch flags on the Agent/subagent tool** (v2.1.139+ line; [What's New](https://code.claude.com/docs/en/whats-new)). The **orchestrator can pass the resolved effort and model directly on each Agent spawn** — no hook mutation required.
- Hooks now see **`$CLAUDE_EFFORT`** and the resolver already consumes it (`thinking_resolver.py`, rule 2a). `settings.autoMode.effortLevel` sets a session default.
- `/model` sets current-session model; `disallowed-tools` is now declarable in skill frontmatter.

So the enforcement that's been "deferred until the schema exposes `modified_tool_input`" can ship **today** by moving the resolved decision from a hook *that can only log* to the orchestrator *that already authors the spawn*. The hook stays as the resolver-of-record and forensic logger; the orchestrator reads the resolved value and passes `--effort`/`--model`.

## Proposed Change

1. **Re-run the probe on the pinned version first (blocking gate).** Confirm `--effort` and `--model` are accepted on Agent spawns on `version-pin` (2.3.0) and that the resolved value is reflected in the rendered trace. Record GREEN/RED in this file's § Findings. Use the operator-driven isolated-session protocol already documented in `probe-result.md` § Re-probe (the subagent-self-modification hazard that made the *hook* probe unsafe does **not** apply to passing a spawn flag).
2. **If GREEN — shift enforcement to the orchestrator, one decision at a time:**
   - **Effort:** orchestrator reads `resolve-thinking.py`'s resolved `effort` (already written to `hook-injections.jsonl`) and passes `--effort <resolved>` on the spawn. The routine budget-3–6 Build/Plan spawns drop from the de-facto default to the gated `high`; `critical OR budget>=N` still promotes to `xhigh` (the #124 gate, now actually applied).
   - **Model:** orchestrator reads `advisor_resolver.py` / `executor_resolver.py`'s resolved executor and passes `--model <sonnet|opus>`. Every budget-<6 code-review moves Opus→Sonnet.
   - **Cache breakpoints:** unchanged by this proposal — the breakpoint injection still depends on the orchestrator-side splice of `rules/core.md` into the prompt body (the `prompt-caching-rules-core-splice` follow-up). Keep it advisory; this proposal does **not** claim to unblock it.
3. **Stage the rollout** — effort first (largest, best-understood), 10-pipeline soak against `eval/baselines`, then model. Each is one PR-sized change behind its existing reversibility env var (`CLAUDE_DISABLE_THINKING_GATE`, `CLAUDE_DISABLE_ADVISOR_GATE`).
4. **If RED on 2.3.0**, close with a documented negative result, correct the stale "v2.1.140 / modified_tool_input" deferral notes in the three hook headers + `CLAUDE.md` to name the *actual* gating fact ("`--effort`/`--model` not accepted on Agent spawns as of 2.3.0"), and pin a re-check to the next minor bump.

## Expected Saving

This is the **single largest weekly-quota lever in the harness**, and it is currently at zero realisation because the gates are log-only:

- **Effort enforcement:** routine Build/Plan spawns drop from default to gated `high`; thinking bills as output (the dominant term). #124 estimated ~20–30% weekly token reduction from this gate alone — *entirely unrealised today.*
- **Model enforcement:** every budget-<6 review moves Opus→Sonnet (~40% cheaper per review, provisional).
- Plausibly the difference between the documented "3 prompts = 18% of weekly quota" and a materially lower burn, because it activates gating the harness **already designed, tested, and shipped to CI** — it just never turned it on.

## Why this is safe

1. **No new decision logic** — the resolvers and their snapshot tests already exist and run in CI. This changes *where the resolved value is applied* (orchestrator spawn flag) not *what it is*.
2. **The orchestrator-flag path avoids the exact hazard that RED'd the hook probe** — passing `--effort` on a spawn does not rewrite `settings.json` or re-enter every PreToolUse hook; it is a per-spawn argument.
3. **Per-decision reversibility already wired** + staged soak + `eval/baselines` quality guard (the same guard #124 used).
4. **Gating only ever lowers cost on routine work**; `critical=true OR budget>=N` still promotes, and `architect`/`security-engineer` model locks are untouched.

## Implementation Checklist (for `/pipeline` run)

1. **Probe (blocking):** operator-driven isolated session per `probe-result.md` § Re-probe — dispatch an Agent with `--effort high --model sonnet`, inspect the rendered trace for the applied values. Record result in § Findings here. Do not proceed on RED.
2. `orchestrator/agent-orchestration.md` + `orchestrator/parallel-dispatch-details.md` — document that the orchestrator reads the resolver's emitted `effort`/`model` from `hook-injections.jsonl` (or re-invokes the resolver lib directly) and passes `--effort`/`--model` on every Agent spawn.
3. Effort flip commit — apply `--effort`; keep `CLAUDE_DISABLE_THINKING_GATE=1` escape. 10-pipeline soak.
4. Model flip commit — apply `--model`; keep `CLAUDE_DISABLE_ADVISOR_GATE=1` escape. 10-pipeline soak.
5. Correct the three hook headers + `CLAUDE.md` § Thinking Defaults / § Advisor-Mode notes to reflect *enforcing via orchestrator flag* (remove the stale "log-only at v2.1.140 pending modified_tool_input" language for effort/model; the cache-breakpoint note stays advisory).
6. `tests/` — assert the orchestrator passes the resolved `--effort`/`--model` on a synthetic ENFORCE decision; assert `critical`/high-budget still promotes.
7. One observation per flip; target ≥15% weekly token reduction across 10 mid-budget pipelines with no `eval/baselines` regression.

## Counter-arguments considered

- **"The probe might RED again on 2.3.0."** Step 1 settles it before any code change. But the flag path is far more likely GREEN than the mutation path — these flags are documented release features, not an unconfirmed hook-schema field.
- **"Why not just wait for `modified_tool_input`?"** Because the saving is large and accruing-as-loss every week it stays off, and the flag path is available now. The hook keeps logging the resolved value either way, so a future mutation-path flip remains possible.
- **"Sonnet reviews miss findings Opus catches."** Gated to budget < 6 (the `model_conditional` arm the harness already defines); soak + baseline guard catch regressions; instant env-var revert.

## Rollback

Set the relevant `CLAUDE_DISABLE_*_GATE=1`; the orchestrator stops passing the flag and the spawn reverts to the model/effort default. Hooks remain log-only. No state migration.

---

**Linked PR for the spec track:** this proposal. Once the probe confirms the flags, dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-28-orchestrator-flag-enforcement.md, effort-flip ONLY (steps 1–3, 5–7). Budget: 7. Critical: true." Then repeat for the model flip.
