# Probe Result — modified_tool_input round-trip on Agent matcher

**Date:** 2026-05-14
**Verdict:** RED
**Captured by:** software-engineer (Build phase, slice C)

## Environment

```
$ claude --version
2.1.141 (Claude Code)
```

## What was probed

Whether `hooks/probe-modified-tool-input.sh`, when registered in
`settings.json` as a `PreToolUse:Agent` matcher, can deliver a
`{"decision":"approve","modified_tool_input":{"thinking":{"effort":"low","display":"omitted"}}}`
envelope to a triggered Agent spawn such that the rendered prompt reflects
the mutated `tool_input.thinking` field.

A GREEN verdict would unlock Slice C-GREEN (resolver `MUTATE` token + wrapper
branches in `pre-agent-thinking.sh` / `pre-agent-advisor.sh`).
A RED verdict reduces Slice C scope to RED-branch only (document the
schema gap; leave thinking + advisor hooks advisory).

## Verdict: RED

**Live probe not safely runnable from within build subagent.** Registering
the probe in `settings.json` would mutate the running harness's PreToolUse
Agent hook table — the subagent triggering an `Agent` tool call to test
the round-trip would also invoke every other registered hook on a freshly-
rewritten `settings.json`, exposing the parent session to potential
breakage across orthogonal hooks. Per Iron Law 4 (REPO_ROOT HEAD on main)
and the build-phase scoping principle, harness self-modification at this
depth requires an operator-driven probe in an isolated session.

**Documentary evidence corroborates RED.**

- `protocols/thinking-defaults.md:101-110` — "empirical reality at v2.1.140:
  the per-spawn `tool_input.thinking.effort` field is **not yet exposed**
  in the Agent tool input schema, so a hard block would refuse every
  orchestrator spawn." v2.1.141 ships unchanged in this respect — the
  `protocols/thinking-defaults.md` text was not updated between v2.1.140
  and v2.1.141.
- `pipeline-state/promote-advisory-hooks-enforcement/architect-context.md`
  § Domain Analysis #4 — "Empirical proof — `exit 2` deny-path WORKS today;
  `modified_tool_input` round-trip UNCONFIRMED." Probe artifacts exist but
  no `pipeline-state/c10-schema-flip-audit/probe-output.json` was ever
  generated.
- Recon anti-finding: "Across all production hooks, only
  `hooks/probe-modified-tool-input.sh:21-23` emits a `modified_tool_input`
  JSON envelope … No production hook mutates `tool_input`." Zero prior
  successful mutation flips.

## Probe script status

`hooks/probe-modified-tool-input.sh` is committed and executable. The
script remains useful for **future operator-run manual verification**:
register temporarily in `settings.json`, trigger a trivial Agent spawn
(e.g. `Glob`), inspect both `/tmp/probe-modified-tool-input-<TS>.log`
AND the rendered spawn behaviour, then unregister. This is the
prerequisite for any future Slice C-GREEN flip.

## Slice C consequences

- **AC-C-AUTHOR (probe script exists)** — GREEN (script committed upstream;
  unchanged by this build phase).
- **AC-C0 (probe-result.md persisted)** — GREEN (this file).
- **AC-C1a, AC-C1b, AC-C2a, AC-C2b (GREEN-conditional)** — `skipped: probe-red`.
  Precedent: `PBT_SKIPPED` reason enum in `rules/verdict-catalog.md`.
- **AC-C3 (RED-conditional)** — GREEN: `protocols/autonomous-intelligence.md`
  updated to cite this file as evidence of the schema gap.
- **AC-C4 (preexisting-red.txt captured)** — GREEN: file at
  `pipeline-state/promote-advisory-hooks-enforcement/preexisting-red.txt`
  with 51 entries, captured at base SHA `1f06df9` before any slice edits.

## Re-probe protocol (post-merge)

A future operator should:

1. Confirm `claude --version` reports a release that names
   `modified_tool_input` on the Agent matcher in its release notes.
2. Register `hooks/probe-modified-tool-input.sh` in `settings.json` as a
   temporary `PreToolUse:Agent` matcher.
3. Trigger a trivial Agent spawn (`Glob` is harmless).
4. Inspect `/tmp/probe-modified-tool-input-*.log` for the captured
   stdin envelope AND inspect the spawn's rendered trace at
   `metrics/{session}/trace/<role>-<task-id>-<ts>.txt` for the mutated
   `tool_input.thinking` field.
5. Unregister the probe from `settings.json` before any other work.
6. If both inspections show the mutation reflected, update this file to
   GREEN and re-run Slice C-GREEN as a follow-up pipeline (resolver
   patches + wrapper branches in `pre-agent-thinking.sh` /
   `pre-agent-advisor.sh`).
