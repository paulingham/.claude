# Thinking Defaults Protocol

Opus 4.7 introduces a `thinking` field on Agent spawns that controls reasoning effort and visibility. This file is the single source of truth for default selection. The pipeline applies defaults via the `pre-agent-thinking.sh` PreToolUse hook on the `Agent` matcher.

## Fields

- `effort`: `low` | `medium` | `high` | `xhigh` — reasoning depth
- `display`: `omitted` | `text` — whether thinking content is shown to the user

## Precedence (highest wins)

1. **Environment override**: `CLAUDE_THINKING_EFFORT` / `CLAUDE_THINKING_DISPLAY` (must be a valid enum value; invalid values are ignored, not raised)
2. **Explicit `thinking` field** on the Agent spawn's `tool_input`
3. **Role-based rules** (combined layer; reports `source="role"` regardless of which sub-rule fires):
   - **3a. Promotions to xhigh**:
     - `architect` + (`critical=true` OR `budget>=7`) → `effort=xhigh`
     - `security-engineer` + `critical=true` AND `budget>=7` → `effort=xhigh`
     - Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` → `effort=xhigh`
     - **Debug active AND debug file age < TTL** (state file `{task_id}-debug.md` exists, mtime within `CLAUDE_DEBUG_DISPLAY_TTL` seconds — default 1800) → `display=text`. **Continuation cycles** (mtime ≥ TTL) → `display=omitted`. Touching the debug file (e.g. recording a new hypothesis) resets the window. Phase=`debugging` without a debug file also forces `display=text`.
   - **3b. Downgrades from default**:
     - `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer`, `security-engineer` (when 3a does not apply) → `effort=high`
     - `planning-agent` → `effort=low`
   - 3a evaluates BEFORE 3b, so a `security-engineer` that meets the promotion gate gets xhigh, not the downgrade.
4. **Hardcoded fallback**: `effort=xhigh`, `display=omitted`. Anthropic's April 23 2026 postmortem set xhigh as the product-level default for Opus 4.7; the harness mirrors that. Sonnet-executor roles are explicitly downgraded by rule 3b.

## Role Defaults Summary

| Role | Default executor | Default effort | xhigh trigger |
|---|---|---|---|
| `architect` | Opus | xhigh | always (critical or budget>=7 still promotes via role layer; default already xhigh below threshold) |
| `software-engineer` | Opus | xhigh | inherits default |
| `frontend-engineer` | Opus | xhigh | inherits default |
| `infrastructure-engineer` | Opus | xhigh | inherits default |
| `security-engineer` | Sonnet (advisor: Opus) | high | critical AND budget>=7 → xhigh (role layer) |
| Best-of-N candidate | varies per slot | high | budget>=7 (any role) → xhigh (role layer) |
| `code-reviewer` | Sonnet (advisor: Opus) | high | never |
| `qa-engineer` | Sonnet | high | never |
| `product-reviewer` | Sonnet | high | never |
| `patch-critic` | Sonnet | high | never |
| `database-engineer` | Sonnet | high | never |
| `planning-agent` | Sonnet | low | never |

A role declared in `instinct_categories` but absent from this table is treated as Opus-default and inherits `xhigh`. The downgrade list in `hooks/_lib/thinking_role.py` is authoritative; the AC7 snapshot test (`DowngradeListMatchesAgentFrontmatter` in `tests/test_thinking_defaults.py`) pins the list to the seven Sonnet-executor agent files — drift in either direction fails CI.

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

## xhigh Allocation Boundary

The boundary is **executor-model**, not build-vs-review. Anthropic's April 23 2026 postmortem set xhigh as the product-level default for Opus 4.7 and `high` for all other models; the harness mirrors that mapping. Any role whose default executor is Opus inherits the xhigh fallback (rule 4); any role whose default executor is Sonnet (or whose iteration economics make xhigh wasteful) is explicitly downgraded by rule 3b.

xhigh **inherited via fallback** by:

- `architect`, `software-engineer`, `frontend-engineer`, `infrastructure-engineer` (Opus executors — `source="default"`)

xhigh **promoted via rule 3a** for:

- `architect` + (`critical=true` OR `budget>=7`) — `source="role"`
- `security-engineer` + `critical=true` AND `budget>=7` — `source="role"`
- Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` — `source="role"`

xhigh **explicitly excluded** for these Sonnet-executor roles (rule 3b downgrades to `high` or `low`, `source="role"`):

- `code-reviewer`, `qa-engineer`, `product-reviewer`, `patch-critic`, `database-engineer` — downgraded to `high`
- `security-engineer` below the critical-AND-budget>=7 threshold — downgraded to `high`
- `planning-agent` (long-lived poll loop) — downgraded to `low`

The downgrade list lives in `hooks/_lib/thinking_role.py` (`_DOWNGRADE_TO_HIGH` and `_DOWNGRADE_TO_LOW`) and is locked against agent-frontmatter drift by the AC7 snapshot test (`DowngradeListMatchesAgentFrontmatter`).

### Forensic / Source-Field Integration Note

Downstream tooling reads `result["source"]` from the resolver — namely `/forensics`, observation-capture in the Reflect step (`learning/{project-hash}/observations.jsonl`), and eval baseline diffs. Both promotions (3a) and downgrades (3b) report `source="role"` because they are produced by the same `role_effort()` callsite. Tooling that needs to differentiate promotion-vs-downgrade must inspect the `effort` value, not the `source` field:

- `source=="role" AND effort=="xhigh"` ⇒ promotion (3a fired)
- `source=="role" AND effort in {"high","low"}` ⇒ downgrade (3b fired)
- `source=="default" AND effort=="xhigh"` ⇒ Opus-executor inheritance (rule 4 fallback)

The source field is intentionally NOT split into a fifth token (`role-promote` / `role-downgrade`) — adding one would invalidate every existing observation record without behavioural payoff. Future refactors may revisit if forensics needs the distinction at scale.
