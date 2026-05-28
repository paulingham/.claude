# Proposal: Branch-on-Retry — Reuse the Failed Trajectory Instead of Cold-Restarting

**Status:** PROPOSED (2026-05-28)
**Owner:** orchestrator-derived recommendation from external research (SWE-Replay arXiv 2601.22129; Scaling Test-Time Compute arXiv 2604.16529)
**Implementation track:** requires `/pipeline` run (touches `protocols/operational-protocol.md` § Error Recovery, `orchestrator/agent-orchestration.md`, the fix-engineer/re-spawn dispatch, light use of the existing `hooks/subagent-stop-trajectory.sh` output)

---

## Problem

The harness's error-recovery rule is **cold restart**: *"Retry twice, then escalate… re-spawn agent with fresh worktree"* (`protocols/operational-protocol.md` § Error Recovery / Escalation). When a Build or fix attempt fails verification, the retry spawn starts from zero — it re-derives the same context, re-explores the same files, and frequently re-discovers the same dead end the first attempt already ruled out. This is **the most expensive possible retry**: it pays full preamble + full exploration cost again, and it throws away the single most valuable artifact the failed attempt produced — *the knowledge of why it failed*.

The harness already **captures** that artifact: `hooks/subagent-stop-trajectory.sh` appends a structured record to `pipeline-state/{task-id}/trajectory.jsonl` on every SubagentStop. It is written for forensics and never read back into a retry.

External 2026 evidence is specific and quantified:

- **SWE-Replay** (arXiv 2601.22129): recycling prior-trial trajectories and *branching* (exploit archived experience vs explore fresh) delivered **up to −17.4% cost with +up to 3.8% perf on SWE-bench Verified**, and **+up to 22.6% perf with −9% cost on Pro/Multilingual** — **no reward model required.**
- **Scaling Test-Time Compute for Agentic Coding** (Meta et al., arXiv 2604.16529): convert each rollout into a **structured summary** (hypotheses tried, progress, failure modes; discard low-signal trace) so a retry can be *seeded* from salient history rather than raw transcript. This is the same long-horizon analog of best-of-N the harness already cites for PDR-RTV.

## Proposed Change

Replace the cold-restart retry with a **summarise-then-branch** retry, bounded by the existing retry-twice budget:

1. **On a verification failure that triggers a retry**, before re-spawning, distil the failed attempt's `trajectory.jsonl` (+ the failing-test stderr the `fix-engineer` Diagnosis block already captures, PR #153) into a compact **failure summary**: `{hypotheses_tried, what_passed, what_failed, ruled_out, last_diff_stat}`. Cap it hard (≤ the observation-length cap precedent, `2026-05-14-observation-length-cap.md`) so the seed is cheap, not a transcript replay.
2. **Seed the retry spawn** with that summary as explicit "prior attempt — do not repeat these dead ends" context. The retry **branches**: it may exploit the prior partial progress (keep the parts that passed) or explore fresh, but it never re-derives the ruled-out paths.
3. **Keep the retry-twice-then-escalate budget unchanged.** This makes each retry *cheaper and more likely to succeed*, it does **not** add retries. Escalation to the user on the third failure is untouched (Iron Law / operational protocol).
4. **Scope to the cases where it pays:** Build slice re-spawn, `fix-engineer` re-dispatch on `CHANGES_REQUESTED`/`SPEC_BLIND_FAILED`/`PATCH_REJECTED`, and the debug loop. Not worktree-corruption re-spawns (those are environmental, no useful trajectory).
5. **Env hatch** `CLAUDE_BRANCH_ON_RETRY=0` reverts to cold restart.

## Expected Effect

- **Both a cost and a correctness lever** — the rare case the harness cares about most (a retry) gets cheaper *and* more likely to land, because the retry no longer burns budget re-walking known-dead paths and arrives pre-informed of the failure mode. SWE-Replay's −9–17% cost with neutral-to-positive perf is the external precedent.
- **Directly serves "verified, not looks-right"** — a retry that *knows why the last attempt failed verification* is far more likely to produce code that actually passes the next verification, rather than a fresh attempt that re-introduces a different version of the same bug.
- **Cheap to build** — the trajectory file already exists; this adds a summariser (one Haiku/cheap call, capped) + a seed into the re-spawn prompt.

## Why this is safe

1. **No change to the retry budget or the escalation gate** — purely changes *what context the retry spawn starts with*. The third-failure → user escalation is untouched.
2. **The seed is advisory context, not a constraint** — the retry agent still authors its own diff under the full ATDD/mutation/spec-blind gates; nothing about the verification floor changes. A bad summary at worst wastes a small capped call.
3. **Reuses committed infrastructure** (`subagent-stop-trajectory.sh`, the fix-engineer Diagnosis block, the observation-length cap pattern). Net new surface is one summariser + one prompt-seed.
4. **Env-hatch reversible**; summaries are capped so a runaway trajectory can't inflate retry cost.

## Implementation Checklist (for `/pipeline` run)

1. `protocols/operational-protocol.md` § Error Recovery — replace "re-spawn fresh" for the in-scope cases with "summarise the failed trajectory (capped), seed the retry"; keep "retry twice, then escalate" verbatim.
2. A trajectory-summariser lib (cheap model call, hard length cap) that reads `pipeline-state/{task-id}/trajectory.jsonl` + the fix-engineer Diagnosis stderr and emits the `{hypotheses_tried, ruled_out, what_passed, what_failed, last_diff_stat}` seed.
3. `orchestrator/agent-orchestration.md` — document that the re-spawn/fix-engineer dispatch includes the seed for in-scope failure verdicts; worktree-corruption re-spawns skip it.
4. `CLAUDE_BRANCH_ON_RETRY` env hatch wired in the dispatch path.
5. `tests/` — fixture trajectory.jsonl → assert the summary contains the failure mode and is under the cap; assert worktree-corruption path does NOT branch; assert retry budget unchanged.
6. Observation after 10 retried pipelines: compare retry success-rate and retry token-cost vs the cold-restart baseline (the SWE-Replay direction-of-effect is the hypothesis to confirm on our own data).

## Counter-arguments considered

- **"A misleading summary could anchor the retry to a wrong path."** The seed is framed as "prior dead ends to avoid," not "the answer is near here," and the retry is free to explore fresh. The verification gates remain the authority; a bad seed wastes one capped call, it can't ship a wrong diff.
- **"Trajectory replay is what PDR-RTV already does."** PDR-RTV is *parallel finalist selection within one Build*; this is *sequential reuse across a failed attempt and its retry*. SWE-Replay (sequential, no reward model) and PDR (parallel) are complementary — 2604.16529 names both.
- **"Adds latency to retries."** The summariser is one cheap capped call against an already-written file; it is strictly cheaper than the cold re-exploration it replaces.

## Rollback

Set `CLAUDE_BRANCH_ON_RETRY=0`; retries revert to cold restart. `trajectory.jsonl` capture is unchanged. No state migration.

---

**Linked PR for the spec track:** this proposal. Dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-28-branch-on-retry.md exactly as specified. Budget: 6. Critical: false."
