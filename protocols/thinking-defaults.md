# Thinking Defaults Protocol

Opus 4.7 introduces a `thinking` field on Agent spawns that controls reasoning effort and visibility. This file is the single source of truth for default selection. The pipeline applies defaults via the `pre-agent-thinking.sh` PreToolUse hook on the `Agent` matcher.

## Fields

- `effort`: `low` | `medium` | `high` | `xhigh` — reasoning depth
- `display`: `omitted` | `text` — whether thinking content is shown to the user

## Adaptive Thinking (Opus 4.7+)

Claude Opus 4.7 and later models reject manual extended thinking
(`thinking: {type: "enabled", budget_tokens: N}`) at the Anthropic API
layer, returning HTTP 400. Adaptive thinking
(`thinking: {type: "adaptive"}`) is the only supported configuration on
those models. The harness MUST NOT introduce `budget_tokens` into any
hook, skill, agent, script, or `settings.json` payload — the rejection
is enforced upstream and any such config will fail every Opus 4.7+
spawn.

Source (verified 2026-05-08): Anthropic Extended Thinking docs at
[`platform.claude.com/docs/en/build-with-claude/extended-thinking`](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
state, verbatim, that for Claude Opus 4.7 and later models *manual extended thinking is no longer supported*
and that callers should "use adaptive thinking
(`thinking: {type: "adaptive"}`) with the effort parameter instead."
The docs also state that manual `budget_tokens` is "no longer accepted
and returns a 400 error" on Opus 4.7+.

**Do not introduce `budget_tokens` into hooks, skills, agents,
scripts, or `settings.json`.** Do not set it on Agent spawn payloads.
Use the `effort` field on `thinking` (resolved by
`hooks/_lib/thinking_resolver.py` and the precedence list below)
instead — adaptive thinking allocates budget at the API layer.

**`CLAUDE_HOOK_PROFILE=minimal` interaction.** When the
`pre-agent-thinking.sh` hook is suppressed (because
`CLAUDE_HOOK_PROFILE=minimal` is set), this guidance still applies —
the rejection happens at the Anthropic API layer regardless of harness
instrumentation. The hook only logs the resolved `effort`/`display`
values for forensic visibility; it never injects `budget_tokens`, and
suppressing it does not unlock manual extended thinking.

**Naming rationale for the `claude-effort-env` source value (forward
reference to rule 2a in the precedence list below).** The existing
`env` source name predates Claude Code's session-level env var;
`claude-effort-env` is name-prefixed to disambiguate which env var
fired. Renaming `env` → `claude-thinking-env` would invalidate every
existing observation record.

## Precedence (highest wins)

1. **Environment override**: `CLAUDE_THINKING_EFFORT` / `CLAUDE_THINKING_DISPLAY` (must be a valid enum value; invalid values are ignored, not raised)
2. **Explicit `thinking` field** on the Agent spawn's `tool_input`
2a. **Claude Code effort env override**: `CLAUDE_EFFORT` (must be a valid enum value drawn from the harness `{low, medium, high, xhigh}` set; invalid values fall through to the next tier). When this tier wins, `source="claude-effort-env"` — distinct from rule 1's `source="env"` so prior observation records remain interpretable. Naming rationale: the existing `env` source name predates Claude Code's session-level env var; `claude-effort-env` is name-prefixed to disambiguate which env var fired. Renaming `env` → `claude-thinking-env` would invalidate every existing observation record. Note: when `CLAUDE_HOOK_PROFILE=minimal` the hook is suppressed, but resolver-direct callers still observe this tier — for hook-independent enforcement use `CLAUDE_THINKING_EFFORT` (rule 1).
3. **Role-based rules** (combined layer; reports `source="role"` regardless of which sub-rule fires):
   - **3a. Promotions to xhigh** (PR #124 narrow-xhigh-promotion 2026-05-14 — gated, no longer unconditional; see `protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md`):
     - `architect` + (`critical=true` OR `budget>=6`) → `effort=xhigh`
     - `software-engineer` + (`critical=true` OR `budget>=7`) → `effort=xhigh`
     - `frontend-engineer` + (`critical=true` OR `budget>=7`) → `effort=xhigh`
     - `infrastructure-engineer` + (`critical=true` OR `budget>=7`) → `effort=xhigh`
     - `security-engineer` + `critical=true` AND `budget>=7` → `effort=xhigh` (conjunctive — distinct operator)
     - Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` → `effort=xhigh`
     - **Debug active AND debug file age < TTL** (state file `{task_id}-debug.md` exists, mtime within `CLAUDE_DEBUG_DISPLAY_TTL` seconds — default 1800) → `display=text`. **Continuation cycles** (mtime ≥ TTL) → `display=omitted`. Touching the debug file (e.g. recording a new hypothesis) resets the window. Phase=`debugging` without a debug file also forces `display=text`.
   - **3b. Downgrades from default**:
     - `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer`, `security-engineer` (when 3a does not apply) → `effort=high`
     - `planning-agent` → `effort=low`
   - 3a evaluates BEFORE 3b, so a `security-engineer` that meets the promotion gate gets xhigh, not the downgrade.
   - The four gated promotions are inlined as explicit clauses in `_is_xhigh()` (`hooks/_lib/thinking_role.py`); `_PROMOTE_TO_XHIGH` is retained as `frozenset()` for the `PromoteToXhighListMatchesAgentFrontmatter` snapshot test, which now pins the unconditional-promotion roster to the empty set.
4. **Hardcoded fallback**: `effort=high`, `display=omitted`. xhigh is allocated only via rule 3a (the four gated build/design promotions on `critical=true OR budget>=N`; security-engineer on `critical=true` AND `budget>=7`; Best-of-N candidates on `budget>=7`). Build/design roles whose gate does not fire (e.g. architect at `critical=false, budget<6`) fall through to this floor — `source="default"` in that case, not `"role"`.

## Role Defaults Summary

| Role | Default executor | Default effort | xhigh trigger |
|---|---|---|---|
| `architect` | Opus | xhigh | `critical=true` OR `budget>=6` → xhigh (role layer 3a) |
| `software-engineer` | Sonnet (advisor: Opus) | xhigh | `critical=true` OR `budget>=7` → xhigh (role layer 3a) |
| `frontend-engineer` | Sonnet (advisor: Opus) | xhigh | `critical=true` OR `budget>=7` → xhigh (role layer 3a) |
| `infrastructure-engineer` | Opus | xhigh | `critical=true` OR `budget>=7` → xhigh (role layer 3a) |
| `security-engineer` | Sonnet (advisor: Opus) | high | `critical=true` AND `budget>=7` → xhigh (role layer 3a) |
| Best-of-N candidate | varies per slot | high | `budget>=7` (any role, name starts with `boN-`) → xhigh (role layer 3a) |
| `code-reviewer` | Sonnet (advisor: Opus) | high | never |
| `qa-engineer` | Sonnet | high | never |
| `product-reviewer` | Sonnet | high | never |
| `patch-critic` | Sonnet | high | never |
| `database-engineer` | Sonnet | high | never |
| `planning-agent` | Sonnet | low | never |

**Column semantics (post-PR #124):** The "Default effort" column for the four gated build/design roles names the **promoted ceiling** when the gate fires, not the floor. When the gate is sub-threshold (e.g. architect at `critical=false, budget<6`), the role falls through to rule 4's hardcoded `high` floor with `source="default"`. The third column thus pins the documented xhigh-promotion roster; the "xhigh trigger" column pins the gate.

A role declared in `instinct_categories` but absent from this table inherits `high` from the rule 4 fallback. Two snapshot tests in `tests/test_thinking_defaults.py` pin the role rosters to `hooks/_lib/thinking_role.py`: `PromoteToXhighListMatchesAgentFrontmatter` locks the four gated xhigh promotions (now empty after PR #124; inlined as clauses in `_is_xhigh()`); `DowngradeListMatchesAgentFrontmatter` locks the remaining seven Sonnet-executor / poll-loop downgrade entries. Drift in either direction fails CI.

`display` defaults to `omitted` for all roles unless a debug state file is active.

`planning-agent` is the lone exception to the `effort=high` floor. It runs a
long-lived poll loop (read scratchpad → diff against plan → Edit when
contradicted) — pattern-matching work, not architectural reasoning. Original
design decisions belong to the architect at Plan phase. Per-poll high-effort
reasoning would burn token budget on a role that does not need it; `low` keeps
iteration fast and the role advisory.

## Hook Behavior (Path B — current, log-only at v2.1.140)

The probe in `pipeline-state/opus47-thinking-defaults-scratchpad/build-probe.md`
selected Path B (validation/block). Empirical reality at **v2.1.140**: the
per-spawn `tool_input.thinking.effort` field is **not yet exposed** in the
Agent tool input schema, so a hard block would refuse every orchestrator
spawn. Every historical `hook-injections.jsonl` record confirms the per-spawn
field is not populated. The hook is therefore **log-only** until Claude Code
lands either `modified_tool_input` (Path A) or per-spawn `thinking` on the
Agent input schema.

What v2.1.140 DOES expose, and what the resolver consumes today:

- `$CLAUDE_EFFORT` env var is consumed via `hooks/_lib/thinking_resolver.py:40`
  (rule 2a, source token `"claude-effort-env"`). Operators can force effort
  on a session basis by exporting this variable.
- `settings.autoMode.effortLevel` session key sets a global default.

What v2.1.140 does NOT expose (and gates promotion-to-enforced):

- Per-spawn `tool_input.thinking.effort` on the Agent PreToolUse input.

Behavioural rules:

- **Missing `thinking` field on an Agent spawn**: resolver resolves effort
  via the precedence list (env → explicit → claude-effort-env → role →
  default), the bash wrapper writes one advisory log entry to
  `metrics/{session}/hook-injections.jsonl` with `source: "logged"`, then
  exits 0. No stderr block message. No spawn refusal.
- **Present `thinking` field**: hook exits 0, no validation.
- **Non-Agent tools**: hook exits 0 immediately.
- **Resolver crash (e.g. `python3` not on PATH)**: hook exits 0 (defensive
  `|| exit 0` fallback in `pre-agent-thinking.sh`). The hook MUST NEVER
  block a spawn it cannot evaluate.

## Current Status

Path B remains **log-only** (advisory) at v2.1.140. The per-spawn
`tool_input.thinking.effort` field is not yet exposed on the Agent tool input
schema, so blocking would refuse every orchestrator spawn — Iron Law 4
(REPO_ROOT HEAD STAYS ON main) makes the brick risk catastrophic.
Promotion-to-enforced is a single-file flip in `hooks/pre-agent-thinking.sh`
once the per-spawn field lands in a future Claude Code release; the
resolver, tests, and precedence rules are unchanged by that flip.

A pre-merge empirical probe of `modified_tool_input` round-trip on the
Agent matcher (`pipeline-state/promote-advisory-hooks-enforcement/probe-result.md`)
returned **RED** on 2026-05-14: the probe could not be executed safely from
inside the build subagent (registering it in `settings.json` would mutate
the running harness's hook table), and documentary evidence at
`protocols/thinking-defaults.md:101-110` confirms the per-spawn schema is
still missing. Operator-run manual verification post-merge is required
before considering a GREEN-branch flip.

## Reversibility Escape

Operators can disable the thinking gate per-session without editing the
hook file by exporting `CLAUDE_DISABLE_THINKING_GATE=1`. The hook
short-circuits to `exit 0` before invoking the resolver, so no
`hook-injections.jsonl` line is appended for the affected spawns. This
mirrors `CLAUDE_DISABLE_TOOL_ALLOWLIST` (see `hooks/pre-agent-allowlist.sh:20`)
and is the canonical run-time rollback if a future enforcement flip
denies a legitimate spawn. The variable is documented alongside the
other PreToolUse Agent escapes in `protocols/agent-protocol.md` § Reversibility Escapes (PreToolUse Agent hooks).

## Environment Variables

| Variable | Effect |
|---|---|
| `CLAUDE_THINKING_EFFORT` | Force effort to `low\|medium\|high\|xhigh`. Invalid values ignored. |
| `CLAUDE_THINKING_DISPLAY` | Force display to `omitted\|text`. Invalid values ignored. |
| `CLAUDE_PIPELINE_STATE_DIR` | Override the directory the resolver scans for `*-pipeline.md` and `{task_id}-debug.md` files. Defaults to `~/.claude/pipeline-state`. |
| `CLAUDE_DEBUG_DISPLAY_TTL` | Override TTL in seconds for time-bounded debug display (default: 1800). Read from env dict in `resolve()`. Non-numeric values fall back to default. |

## Implementation

- `hooks/_lib/thinking_resolver.py` — pure precedence engine, no I/O. `resolve(tool_input, env, state, now=None) -> {effort, display, source}`. `now` defaults to `time.time()`; tests inject explicit values.
- `hooks/_lib/thinking_debug_display.py` — TTL-bounded debug display helper. `debug_display(state, env, now) -> "text"|None`.
- `hooks/_lib/pipeline_state.py` — discovers active pipeline state file, parses frontmatter, detects debug, reports `debug_mtime`. `read_active_state(state_dir=None) -> dict`.
- `hooks/_lib/resolve-thinking.py` — stdin entry script that ties the two together.
- `hooks/pre-agent-thinking.sh` — bash wrapper registered in `settings.json` under `PreToolUse > Agent`.
- Tests: `tests/test_thinking_defaults.py` (resolver suite + hook log-only behavior).

Note: teammate (TaskCreate) dispatches are covered transparently because teammates are spawned via the `Agent` tool (with `team_name` + `name`) per `rules/parallel-dispatch-protocol.md`. The hook does not register on `TaskCreate` — it doesn't need to.

## xhigh Allocation Policy

xhigh is the **default floor for primary build and design roles** as of May 2026, and remains a **gated promotion** for review/critic work. Two pieces of evidence drive the split:

1. **Apr 23 2026 cost/quality postmortem** — measured promotion-on-trigger lift was concentrated in stakes-bearing and ambiguity-bearing work. Build engineers (`software-engineer`, `frontend-engineer`, `infrastructure-engineer`) hit those triggers on most non-trivial work but were dispatched at `high` because the historical policy treated xhigh-on-Opus as a premium spend.
2. **May 2026 Anthropic Opus 4.7 adaptive-thinking guidance** — Opus 4.7 rejects manual `budget_tokens` (HTTP 400) and the API exposes only `effort`. Adaptive thinking allocates budget at the API layer, so the harness no longer pays a wall-clock-and-tokens premium for `effort=xhigh` on routine implementation; the floor moved.

Combining (1) and (2): the four primary build/design roles — `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` — are **gated to xhigh on `critical=true OR budget>=N`** via rule 3a (PR #124 narrow-xhigh-promotion 2026-05-14, supersedes the prior May 2026 unconditional policy). They remain stakes-bearing or ambiguity-bearing on stakes-bearing pipelines; on routine sub-threshold work they fall through to the `high` floor so the harness does not pay the per-spawn xhigh premium on every Build/Plan spawn. See `protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` for the cost rationale.

xhigh is still **rationed** for the rest of the role table. Review/critic/database/planning roles inherit `high` (or `low` for planning-agent) because:

- **Review work is iteration-bounded.** A reviewer scanning a diff against a checklist does not benefit from deeper search the way an architect choosing among alternatives does.
- **Database work is contract-bounded.** Migration safety, query plans, and index choices follow established patterns — the win is correctness against a checklist, not novel design.
- **Poll loops are pattern-matching.** `planning-agent` re-reads a plan against scratchpad findings hundreds of times per pipeline; per-poll xhigh is pure waste.

The earlier "xhigh is **not** the default for Opus work" position is superseded for the four build/design roles. It still holds for the rest. `security-engineer` retains its dual treatment — `high` by default, xhigh only under the existing `critical=true AND budget>=7` gate — because security review is checklist-driven on routine work and benefits from depth only at high stakes. Best-of-N candidates retain their `budget>=7` gate for the same reason.

See **`pipeline-state/opus47-xhigh-default/plan.md`** for the slice that landed this policy and the Apr 23 / May 2026 evidence trail.

## xhigh Allocation Boundary

The boundary is **role-class**, not executor-model. Build and design roles get xhigh when a per-role gate fires (PR #124 narrow promotion: `critical=true OR budget>=N`); review, critic, database, and poll-loop roles stay on the high (or low) floor unless a specific gate fires. The rule 4 fallback applies to roles absent from any 3a/3b sub-rule AND to build/design roles whose gate did not fire — in the latter case `source="default"`, not `"role"`.

xhigh **never inherited via fallback**. No role gets xhigh from rule 4.

xhigh **promoted via rule 3a disjunctively** for the four primary build/design roles (PR #124 narrow-xhigh-promotion 2026-05-14):

- `architect` + (`critical=true` OR `budget>=6`) — `source="role"`
- `software-engineer` + (`critical=true` OR `budget>=7`) — `source="role"`
- `frontend-engineer` + (`critical=true` OR `budget>=7`) — `source="role"`
- `infrastructure-engineer` + (`critical=true` OR `budget>=7`) — `source="role"`

xhigh **promoted via rule 3a conjunctively** (distinct operator — AND not OR):

- `security-engineer` + `critical=true` AND `budget>=7` — `source="role"`
- Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` — `source="role"`

`high` **explicitly applied via rule 3b** for review/critic/database roles (`source="role"`, redundant with rule 4 today but retained as the documented intent so a future rule-4 change cannot silently re-promote them):

- `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer` — `high`
- `security-engineer` below the critical-AND-budget>=7 threshold — `high`

`low` **explicitly applied via rule 3b** for:

- `planning-agent` (long-lived poll loop) — `low`

Both rosters live in `hooks/_lib/thinking_role.py`: the four gated promotions are inlined as explicit clauses in `_is_xhigh()`, `_PROMOTE_TO_XHIGH` is retained as `frozenset()` for the snapshot guard, and `_DOWNGRADE_TO_HIGH` / `_DOWNGRADE_TO_LOW` pin the seven downgrades. The snapshot tests `PromoteToXhighListMatchesAgentFrontmatter` and `DowngradeListMatchesAgentFrontmatter` lock both against drift.

### Forensic / Source-Field Integration Note

Downstream tooling reads `result["source"]` from the resolver — namely `/harness:forensics`, observation-capture in the Reflect step (`learning/{project-hash}/observations.jsonl`), and eval baseline diffs. Both promotions (3a) and downgrades (3b) report `source="role"` because they are produced by the same `role_effort()` callsite. Tooling that needs to differentiate promotion-vs-downgrade must inspect the `effort` value, not the `source` field:

- `source=="role" AND effort=="xhigh"` ⇒ promotion (3a fired)
- `source=="role" AND effort in {"high","low"}` ⇒ downgrade (3b fired)
- `source=="default" AND effort=="high"` ⇒ rule 4 fallback (no role rule applied)
- `source=="claude-effort-env" AND effort in {"low","medium","high","xhigh"}` ⇒ Claude Code session effort env-var override (rule 2a fired). The `claude-effort-env` token is name-prefixed to disambiguate from rule 1's `env` token (`CLAUDE_THINKING_EFFORT`). See rule 2a in `## Precedence` for the naming rationale.

The source field is intentionally NOT split into a fifth token (`role-promote` / `role-downgrade`) — adding one would invalidate every existing observation record without behavioural payoff. Future refactors may revisit if forensics needs the distinction at scale.

## Beta header — consumer outside repo, in-tree wire emission shipped 2026-05-15

The Anthropic `effort` parameter on adaptive thinking is gated server-side
by the beta header `anthropic-beta: effort-2025-11-24`. The runtime
consumer of that header — the Claude Code binary that constructs the API
request — lives outside this repo, so flipping the header on every spawn
is a Claude Code release task, not a harness task. Slice B (Opus 4.5
migration) keeps that consumer change ESCALATED.

What this slice ships **in-tree**: `hooks/pre-agent-thinking.sh` annotates
`metrics/{session}/hook-injections.jsonl` with two new fields under
`resolved`:

- `resolved.beta_header` — the literal token `effort-2025-11-24` whenever
  the resolved effort is effort-enabled (any role NOT in the role-disable
  downgrade set whose effort floor is `low`). Absent (field not present,
  not null) for `planning-agent` and any future role demoted to `low` via
  rule 3b — these roles opt out of extended-thinking capability.
- `resolved.api_effort` — mirrors the resolved effort (`low | medium |
  high | xhigh`). The harness `xhigh` is the same wire value as `high` at
  the API layer today; the field is present so downstream binary releases
  can read a single field per spawn without re-resolving the role table.

This is observable preparation work: the JSONL annotation lets us measure
beta-header usage against pipeline outcomes BEFORE the Claude Code binary
starts sending the header. When the binary release lands, the harness
will already have weeks of `beta_header` annotations to cross-reference
with cost and verdict data.

## Named deviation: high floor preserved on review/critic/architect

Slice B (Opus 4.5 migration) carried an operator AC that read "default
medium, promote to high via `critical=true OR budget>=N`". Reality on
this branch keeps the existing `high` floor for `code-reviewer`,
`security-engineer`, and `architect`:

- `code-reviewer` + `security-engineer` are pinned via the
  `_DOWNGRADE_TO_HIGH` frozenset in `hooks/_lib/thinking_role.py`.
- `architect` resolves to `high` via the rule 4 hardcoded fallback when
  the xhigh gate (`critical=true OR budget>=6`) does not fire — it is
  NOT in `_DOWNGRADE_TO_HIGH`, but the fallback floor produces the same
  observable effort.

**Why not lower to medium**: all three roles gate Iron Law surfaces.
Reducing the floor is a quality regression with no offsetting cost win
— these are review/critic/design spawns, dispatched once per phase, not
parallel build fan-outs. The cost differential at `high` vs `medium` on
a single Opus review spawn is small; the quality differential on a
missed review finding is large.

**Verification token**: the Reflect step writes
`metrics/{session}/reflect-tokens/slice-b-high-floor-named-deviation.json`
with initial `acknowledged: false`. The orchestrator's Reflect gate halts
when an unacknowledged token is present — the operator flips it to
`true` to acknowledge the named deviation, or rejects and the pipeline
re-enters Plan. Emission is via `hooks/reflect-token-emit.sh`; the gate
itself is `hooks/reflect-gate-acknowledgment.sh`, invoked at
`protocols/reflection-protocol.md` § 6d-bis (before scratchpad cleanup).

## Postmortem note (May 2026)

The four gated promotions reflect the **Apr 23 2026** cost/quality data — promotion-on-trigger lift was concentrated in stakes-bearing build/design work — combined with the **Opus 4.7** adaptive-thinking floor change (manual `budget_tokens` rejected at the API layer; adaptive thinking allocates budget dynamically). The May 2026 unconditional-promotion policy over-corrected: empirical cost forensics (PR #124) showed routine mid-budget pipelines spent ~18% of weekly Max 20x output on xhigh spawns whose stakes did not warrant the floor. PR #124 restores the cost gate for sub-threshold spawns (`critical=false AND budget<N` → `high`) while preserving xhigh for stakes-bearing work (`critical=true OR budget>=N`).

## Advisory status at v2.1.140

The hook is **advisory/log-only at v2.1.140** — the per-spawn `tool_input.thinking.effort` field is **not yet exposed** on the Agent tool input schema, so resolved effort/display values are written to `metrics/{session}/hook-injections.jsonl` but no spawn is blocked. `$CLAUDE_EFFORT` env var IS consumed (resolver rule 2a, source token `"claude-effort-env"`); `settings.autoMode.effortLevel` session key sets a global default. Will be promoted to enforcement via a single-file flip in `hooks/pre-agent-thinking.sh` once the per-spawn field is exposed in a future Claude Code release.
