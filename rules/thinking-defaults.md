# Thinking Defaults Protocol

Opus 4.7 introduces a `thinking` field on Agent spawns that controls reasoning effort and visibility. This file is the single source of truth for default selection. The pipeline applies defaults via the `pre-agent-thinking.sh` PreToolUse hook on the `Agent` matcher.

## Fields

- `effort`: `low` | `medium` | `high` | `xhigh` — reasoning depth
- `display`: `omitted` | `text` — whether thinking content is shown to the user

## Precedence (highest wins)

1. **Environment override**: `CLAUDE_THINKING_EFFORT` / `CLAUDE_THINKING_DISPLAY` (must be a valid enum value; invalid values are ignored, not raised)
2. **Explicit `thinking` field** on the Agent spawn's `tool_input`
3. **Pipeline-state-derived rules**:
   - **Debug active** (state file `{task_id}-debug.md` exists OR pipeline phase is `debugging`) → `display=text`
   - **Critical task and budget gate**:
     - `architect` + (`critical=true` OR `budget>=7`) → `effort=xhigh`
     - `security-engineer` + `critical=true` AND `budget>=7` → `effort=xhigh`
     - Best-of-N candidates (`name` starts with `boN-`) + `budget>=7` → `effort=xhigh`
4. **Hardcoded fallback**: `effort=high`, `display=omitted`

## Role Defaults Summary

| Role | Default effort | xhigh trigger |
|---|---|---|
| `architect` | high | critical OR budget>=7 |
| `security-engineer` | high | critical AND budget>=7 |
| Best-of-N candidate | high | budget>=7 (any role) |
| `software-engineer` | high | never (xhigh leakage protection) |
| `frontend-engineer` | high | never |
| `code-reviewer` | high | never |
| `qa-engineer` | high | never |
| `product-reviewer` | high | never |
| `database-engineer` | high | never |
| `infrastructure-engineer` | high | never |

`display` defaults to `omitted` for all roles unless a debug state file is active.

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

## Implementation

- `hooks/_lib/thinking_resolver.py` — pure precedence engine, no I/O. `resolve(tool_input, env, state) -> {effort, display, source}`.
- `hooks/_lib/pipeline_state.py` — discovers active pipeline state file, parses frontmatter, detects debug. `read_active_state(state_dir=None) -> dict`.
- `hooks/_lib/resolve-thinking.py` — stdin entry script that ties the two together.
- `hooks/pre-agent-thinking.sh` — bash wrapper registered in `settings.json` under `PreToolUse > Agent`.
- Tests: `tests/test_thinking_defaults.py` (resolver suite + hook log-only behavior).

Note: teammate (TaskCreate) dispatches are covered transparently because teammates are spawned via the `Agent` tool (with `team_name` + `name`) per `rules/parallel-dispatch-protocol.md`. The hook does not register on `TaskCreate` — it doesn't need to.

## xhigh Leakage Boundary

xhigh is reserved for design-quality decisions (architect) and security audits (security-engineer) under elevated stakes, plus best-of-N candidates competing on quality. It is NEVER applied to:

- `software-engineer` / `frontend-engineer` / `database-engineer` / `infrastructure-engineer` (regardless of budget)
- `code-reviewer` / `qa-engineer` / `product-reviewer` (these roles operate on completed work, not design)
- `architect` below the critical-or-budget>=7 threshold
- `security-engineer` below the critical-AND-budget>=7 threshold

This boundary is locked in by tests #13, #14, #15, #20 in `tests/test_thinking_defaults.py`.
