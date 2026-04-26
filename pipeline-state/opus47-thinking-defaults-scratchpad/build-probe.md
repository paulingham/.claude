---
category: decision
---

# Probe Result: Path B selected (validation/block)

## What was probed
Whether a PreToolUse hook on the `Agent` matcher can inject a `thinking` field into
`tool_input` via the `modified_tool_input` mechanism (`{"decision":"approve","modified_tool_input":{...}}` on stdout).

## Why Path B was selected (without empirical run)
The software-engineer agent role has `Agent` and `Skill` in `disallowedTools` — the build agent CANNOT spawn an Agent itself to run the probe. Step 0 of the plan permits this exact case: **"If you cannot empirically verify (e.g., trace not available), document this and DEFAULT to Path B (validation/block)."**

Path B is the conservative design:
- Hook reads stdin JSON of the Agent spawn
- If the spawn is missing `tool_input.thinking.effort` or `tool_input.thinking.display`, the hook exits 2 with a stdout reason instructing the orchestrator to populate the field with the resolved defaults
- The hook calls the same Python resolver that Path A would have used for injection, so the *recommended* effort/display is computed deterministically and surfaced in the block reason
- Documentation in spawn templates becomes the primary mechanism for orchestrator compliance (per plan)
- Refusals are logged to `metrics/{session}/hook-injections.jsonl` with `source: "blocked"`

## Probe artifact retained
`hooks/probe-modified-tool-input.sh` is committed for future use: a human can register it in settings.json under `PreToolUse > Agent`, spawn an Agent, then inspect `/tmp/probe-modified-tool-input-*.log` AND the agent's prompt trace under `~/.claude/metrics/{session}/trace/agent-*.txt` to confirm whether `thinking` arrived in the rendered prompt. If Path A is later validated, only `hooks/pre-agent-thinking.sh` needs to switch from exit-2 to stdout JSON emission — the resolver and tests are unchanged.

## Path B impact on tests
All 20 tests in the plan target the **resolver** (`hooks/_lib/thinking_resolver.py`), not the wire format. The resolver returns `{effort, display, source}` regardless of Path A vs B. Only the bash hook's exit-code/stdout shape differs between paths, and that is covered by hook regression tests, not the Python suite.

## Settings.json registration
Path B hook is registered identically to Path A — both fire on `PreToolUse > Agent`. The difference is in stdout/exit semantics, not registration.
