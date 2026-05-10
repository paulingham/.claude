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
   - **3a. Promotions to xhigh**:
     - `architect` → `effort=xhigh` **unconditionally** (May 2026 Opus 4.7 floor change)
     - `software-engineer` → `effort=xhigh` **unconditionally** (May 2026)
     - `frontend-engineer` → `effort=xhigh` **unconditionally** (May 2026)
     - `infrastructure-engineer` → `effort=xhigh` **unconditionally** (May 2026)
     - `security-engineer` + `critical=true` AND `budget>=7` → `effort=xhigh`
     - Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` → `effort=xhigh`
     - **Debug active AND debug file age < TTL** (state file `{task_id}-debug.md` exists, mtime within `CLAUDE_DEBUG_DISPLAY_TTL` seconds — default 1800) → `display=text`. **Continuation cycles** (mtime ≥ TTL) → `display=omitted`. Touching the debug file (e.g. recording a new hypothesis) resets the window. Phase=`debugging` without a debug file also forces `display=text`.
   - **3b. Downgrades from default**:
     - `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer`, `security-engineer` (when 3a does not apply) → `effort=high`
     - `planning-agent` → `effort=low`
   - 3a evaluates BEFORE 3b, so a `security-engineer` that meets the promotion gate gets xhigh, not the downgrade.
   - The four unconditional promotions are pinned in `hooks/_lib/thinking_role.py` as the `_PROMOTE_TO_XHIGH` frozenset; the snapshot test `PromoteToXhighListMatchesAgentFrontmatter` locks the membership.
4. **Hardcoded fallback**: `effort=high`, `display=omitted`. xhigh is allocated only via rule 3a (the four unconditional build/design promotions; security-engineer on `critical=true` AND `budget>=7`; Best-of-N candidates on `budget>=7`). Roles absent from any 3a/3b sub-rule fall through to this floor.

## Role Defaults Summary

| Role | Default executor | Default effort | xhigh trigger |
|---|---|---|---|
| `architect` | Opus | xhigh | always (rule 3a, unconditional) |
| `software-engineer` | Sonnet (advisor: Opus) | xhigh | always (rule 3a, unconditional) |
| `frontend-engineer` | Sonnet (advisor: Opus) | xhigh | always (rule 3a, unconditional) |
| `infrastructure-engineer` | Opus | xhigh | always (rule 3a, unconditional) |
| `security-engineer` | Sonnet (advisor: Opus) | high | `critical=true` AND `budget>=7` → xhigh (role layer 3a) |
| Best-of-N candidate | varies per slot | high | `budget>=7` (any role, name starts with `boN-`) → xhigh (role layer 3a) |
| `code-reviewer` | Sonnet (advisor: Opus) | high | never |
| `qa-engineer` | Sonnet | high | never |
| `product-reviewer` | Sonnet | high | never |
| `patch-critic` | Sonnet | high | never |
| `database-engineer` | Sonnet | high | never |
| `planning-agent` | Sonnet | low | never |

A role declared in `instinct_categories` but absent from this table inherits `high` from the rule 4 fallback. Two snapshot tests in `tests/test_thinking_defaults.py` pin the role rosters to `hooks/_lib/thinking_role.py`: `PromoteToXhighListMatchesAgentFrontmatter` locks the four unconditional xhigh promotions; `DowngradeListMatchesAgentFrontmatter` locks the remaining seven Sonnet-executor / poll-loop downgrade entries. Drift in either direction fails CI.

`display` defaults to `omitted` for all roles unless a debug state file is active.

`planning-agent` is the lone exception to the `effort=high` floor. It runs a
long-lived poll loop (read scratchpad → diff against plan → Edit when
contradicted) — pattern-matching work, not architectural reasoning. Original
design decisions belong to the architect at Plan phase. Per-poll high-effort
reasoning would burn token budget on a role that does not need it; `low` keeps
iteration fast and the role advisory.

## Hook Behavior (Path B — current, log-only)

The probe in `pipeline-state/opus47-thinking-defaults-scratchpad/build-probe.md`
selected Path B (validation/block). Empirical reality: the Agent tool input
schema does not currently expose `thinking`, so a hard block refused every
orchestrator spawn. The hook is therefore **log-only** until Claude Code lands
either `modified_tool_input` (Path A) or `thinking` in the Agent schema.

- **Missing `thinking` field on an Agent spawn**: hook exits 0 and logs the
  resolved `{effort, display}` to `metrics/{session}/hook-injections.jsonl`
  with `source: "logged"`. No stderr block message. No spawn refusal.
- **Present `thinking` field**: hook exits 0, no validation.
- **Non-Agent tools**: hook exits 0 immediately.

## Current Status

Path B is currently **log-only** (advisory). The Agent tool input schema does
not expose `thinking`, so blocking would refuse every orchestrator spawn. The
hook will be promoted to enforcement (Path A silent injection or hard-block
Path B) when Claude Code exposes the `thinking` field on Agent inputs. When
that happens, only `hooks/pre-agent-thinking.sh` flips behavior — the
resolver, tests, and precedence rules are unchanged.

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

Combining (1) and (2): the four primary build/design roles — `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` — are **unconditionally promoted** to xhigh via rule 3a. They are stakes-bearing or ambiguity-bearing on most spawns, and adaptive thinking removed the cost gate that previously justified per-spawn rationing.

xhigh is still **rationed** for the rest of the role table. Review/critic/database/planning roles inherit `high` (or `low` for planning-agent) because:

- **Review work is iteration-bounded.** A reviewer scanning a diff against a checklist does not benefit from deeper search the way an architect choosing among alternatives does.
- **Database work is contract-bounded.** Migration safety, query plans, and index choices follow established patterns — the win is correctness against a checklist, not novel design.
- **Poll loops are pattern-matching.** `planning-agent` re-reads a plan against scratchpad findings hundreds of times per pipeline; per-poll xhigh is pure waste.

The earlier "xhigh is **not** the default for Opus work" position is superseded for the four build/design roles. It still holds for the rest. `security-engineer` retains its dual treatment — `high` by default, xhigh only under the existing `critical=true AND budget>=7` gate — because security review is checklist-driven on routine work and benefits from depth only at high stakes. Best-of-N candidates retain their `budget>=7` gate for the same reason.

See **`pipeline-state/opus47-xhigh-default/plan.md`** for the slice that landed this policy and the Apr 23 / May 2026 evidence trail.

## xhigh Allocation Boundary

The boundary is **role-class**, not executor-model. Build and design roles get xhigh unconditionally (the May 2026 floor); review, critic, database, and poll-loop roles stay on the high (or low) floor unless a specific gate fires. The rule 4 fallback applies only to roles absent from any 3a/3b sub-rule.

xhigh **never inherited via fallback**. No role gets xhigh from rule 4.

xhigh **promoted via rule 3a unconditionally** for the four primary build/design roles:

- `architect` — `source="role"` (May 2026 unconditional)
- `software-engineer` — `source="role"` (May 2026 unconditional)
- `frontend-engineer` — `source="role"` (May 2026 unconditional)
- `infrastructure-engineer` — `source="role"` (May 2026 unconditional)

xhigh **promoted via rule 3a conditionally** (gate must fire):

- `security-engineer` + `critical=true` AND `budget>=7` — `source="role"`
- Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` — `source="role"`

`high` **explicitly applied via rule 3b** for review/critic/database roles (`source="role"`, redundant with rule 4 today but retained as the documented intent so a future rule-4 change cannot silently re-promote them):

- `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer` — `high`
- `security-engineer` below the critical-AND-budget>=7 threshold — `high`

`low` **explicitly applied via rule 3b** for:

- `planning-agent` (long-lived poll loop) — `low`

Both rosters live in `hooks/_lib/thinking_role.py`: `_PROMOTE_TO_XHIGH` (the four unconditional promotions) and `_DOWNGRADE_TO_HIGH` / `_DOWNGRADE_TO_LOW` (the seven downgrades). The snapshot tests `PromoteToXhighListMatchesAgentFrontmatter` and `DowngradeListMatchesAgentFrontmatter` lock both against drift.

### Forensic / Source-Field Integration Note

Downstream tooling reads `result["source"]` from the resolver — namely `/forensics`, observation-capture in the Reflect step (`learning/{project-hash}/observations.jsonl`), and eval baseline diffs. Both promotions (3a) and downgrades (3b) report `source="role"` because they are produced by the same `role_effort()` callsite. Tooling that needs to differentiate promotion-vs-downgrade must inspect the `effort` value, not the `source` field:

- `source=="role" AND effort=="xhigh"` ⇒ promotion (3a fired)
- `source=="role" AND effort in {"high","low"}` ⇒ downgrade (3b fired)
- `source=="default" AND effort=="high"` ⇒ rule 4 fallback (no role rule applied)
- `source=="claude-effort-env" AND effort in {"low","medium","high","xhigh"}` ⇒ Claude Code session effort env-var override (rule 2a fired). The `claude-effort-env` token is name-prefixed to disambiguate from rule 1's `env` token (`CLAUDE_THINKING_EFFORT`). See rule 2a in `## Precedence` for the naming rationale.

The source field is intentionally NOT split into a fifth token (`role-promote` / `role-downgrade`) — adding one would invalidate every existing observation record without behavioural payoff. Future refactors may revisit if forensics needs the distinction at scale.
