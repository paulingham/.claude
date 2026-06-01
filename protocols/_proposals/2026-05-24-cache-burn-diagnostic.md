# Proposal: Cache-TTL Regression Detector + Opus 4.7 Tokenizer Inflation Note

**Status:** PROPOSED (2026-05-24)
**Owner:** orchestrator-derived recommendation from external research (community log audits)
**Implementation track:** requires `/harness:pipeline` run (touches `skills/cache-audit`, `statusline-command.sh`, `CLAUDE.md` capacity note)

---

## Problem

Two externally-sourced cost facts (2026-04/05) are not yet visible to the harness's telemetry, and either could dominate the "3 prompts = 18% of weekly quota" datapoint:

1. **Prompt-cache TTL regression (community-documented, Anthropic-unconfirmed).** Multiple independent log audits report Claude Code silently moved the default cache TTL from 1h to 5m around late Feb 2026, and **pinned sub-agent dispatches to a 5m TTL since ~April 9**. Effect: on any session where the gap between turns (or between a parent turn and a sub-agent return) exceeds 5 minutes, the prefix is **re-written at 1.25× input instead of re-read at 0.1× input** — a 20–32% cache-creation cost increase in the audited logs, with some Max 20x windows draining far faster than expected. A heavy parallel-fan-out harness (Final Gate = 5 subagents, Review = 2, Best-of-N = 2–3) is maximally exposed: every subagent that returns after 5m forces a parent-prefix rewrite.
   - Sources: github.com/anthropics/claude-code issues #46829, #41788, #41930; recca0120 log audits (2026-04-14, 2026-04-26).
2. **Opus 4.7 tokenizer inflation.** Opus 4.7 ships a new tokenizer that can emit **up to 35% more tokens for the same input** vs 4.6. The `$5/$25` headline is unchanged, but real tokens-per-request — i.e. **quota burn** — can rise 0–35%. The harness's `eval/baselines` "80% claim" cost basis and any capacity forecast predate this.
   - Source: finout.io / cloudzero.com Opus 4.7 pricing analyses (2026-04).

The harness already records the raw signal: `hooks/cost-feed.sh` writes `cache_read_input_tokens` / `cache_creation_input_tokens` per spawn to `metrics/{session}/cache.jsonl`, and `/harness:cache-audit` computes `read_ratio` against `READ_RATIO_TARGET = 0.65`. What's missing is a **regression-shaped alert**: a high `cache_creation : cache_read` ratio *on resumed or multi-subagent sessions* is the 5m-TTL fingerprint, and nothing surfaces it loudly.

## Proposed Change

1. **Add a TTL-regression detector to `/harness:cache-audit`.** Beyond the existing below-target read-ratio list, flag any session where `cache_creation_input_tokens / max(cache_read_input_tokens, 1) > REWRITE_RATIO_ALERT` (start at `0.5`, i.e. rewrites are >50% of reads) **and** the session spans ≥2 subagent dispatches or a >5-minute inter-turn gap. Emit a named verdict line in the report: *"Cache-rewrite bleed detected in N sessions — likely 5m-TTL exposure; see mitigations."*
2. **Surface a one-glyph cache-health indicator in `statusline-command.sh`** (it already renders session telemetry): green when read_ratio ≥ target, amber when the rewrite-ratio alert trips. Cheap, always-visible early warning.
3. **Document mitigations** in `protocols/cost-discipline.md` (don't auto-apply any third-party proxy):
   - Keep the spawn preamble byte-stable (the May 8 subagent-summary cache fix already depends on this — call out the drift surfaces: agent frontmatter, session-memory sync, instinct ordering).
   - Prefer fewer, longer-lived subagent turns over many short ones where correctness allows, to stay inside the 5m window.
   - **Note, do not adopt without review**, the community `claude-code-cache-fix` localhost proxy (`ANTHROPIC_BASE_URL` override, reportedly 82%→95.5% warm hit-rate) as an *unaudited* option, with an explicit "vet before routing traffic" warning.
4. **Add a capacity-planning note to `CLAUDE.md`** recording the Opus 4.7 +0–35% tokenizer inflation, so the next baseline re-run and any weekly-quota forecast account for it rather than assuming flat token counts.

## Expected Saving

- The detector itself saves nothing — it makes an *external, possibly-dominant* burn source **visible and attributable**, which is the precondition for every other cost decision. If the 5m-TTL fingerprint is present, recovering those rewrites to reads is a ~90% saving on the affected prefix segment (0.1× read vs 1.25× write).
- The tokenizer note prevents silent 0–35% under-forecasting of weekly quota — the difference between "we have 2 days of headroom" and running out.

## Why this is safe

1. **Read-only telemetry.** The detector reads `cache.jsonl` the harness already writes; it adds a report section and a statusline glyph. No spawn behaviour changes.
2. **`READ_RATIO_TARGET` single-source discipline is preserved** — the new `REWRITE_RATIO_ALERT` constant lives once in `skills/cache-audit/SKILL.md` § Step 1 alongside it, same staged-flip governance.
3. **No third-party code is wired in.** The proxy is documented as an explicitly-unaudited option, not a default.

## Implementation Checklist (for `/harness:pipeline` run)

1. `skills/cache-audit/SKILL.md` — define `REWRITE_RATIO_ALERT = 0.5` next to `READ_RATIO_TARGET`; add a `## Cache-Rewrite Bleed` report section computing the per-session rewrite ratio + multi-subagent/gap heuristic; render the verdict sentence verbatim with the literal threshold.
2. `skills/cache-audit/tests/` — add fixtures: one clean session (high read-ratio, low rewrite) and one 5m-TTL-shaped session (high rewrite, multi-subagent); assert the detector fires only on the latter.
3. `statusline-command.sh` — add the amber/green cache-health glyph sourced from the most recent `cache.jsonl`; keep it cheap (no extra API calls).
4. `protocols/cost-discipline.md` — add § Cache-TTL Mitigations (byte-stable preamble, longer turns, the unaudited-proxy note with warning).
5. `CLAUDE.md` § Cost Discipline — one-line Opus 4.7 tokenizer-inflation capacity note + pointer to cost-discipline.md.
6. Run `/harness:cache-audit` on the last 30 days of `metrics/` post-merge; if the bleed detector fires, open an observation quantifying the exposure and decide on mitigation #3.

## Counter-arguments considered

- **"The TTL regression is unconfirmed by Anthropic."** Correct — which is why this ships a *detector*, not a fix. If the fingerprint is absent in our own logs, we've spent one cheap audit and ruled it out. If present, we've found a major leak others missed.
- **"Statusline glyph adds clutter."** One character, gated to amber only when the alert trips; it is silent in the healthy case.

## Rollback

Remove the `## Cache-Rewrite Bleed` section and the statusline glyph; the underlying `cache.jsonl` telemetry and `read_ratio` reporting are unchanged. No state migration.

---

**Linked PR for the spec rewrite track:** this proposal. Dispatch `/harness:pipeline` with prompt: "Implement protocols/_proposals/2026-05-24-cache-burn-diagnostic.md exactly as specified. Budget: 5. Critical: false."
