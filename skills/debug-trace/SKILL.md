---
name: "debug-trace"
description: "Toggle prompt tracing on/off for the current session. Tracing captures the rendered spawn prompt for every Agent and Skill invocation to ~/.claude/metrics/{session-id}/trace/. Off by default; enable when debugging agent failures or unexpected verdicts."
argument-hint: "on | off"
---

# Debug Trace Toggle

## What This Skill Does

Flips `CLAUDE_ENABLE_TRACE` for the current session. When on, the `trace-prompt.sh` PreToolUse hook (registered on `Agent|Skill` matchers) writes the fully-rendered spawn prompt to `metrics/{session-id}/trace/{role}-{task-id}-{timestamp}.txt`. When off, the hook fast-exits — zero overhead.

Tracing is off by default because the captured prompts can be large, contain sensitive data (instinct bodies, scratchpad findings, session memory), and are only useful when actively debugging agent behaviour.

## When to Invoke

- An agent returned an unexpected verdict and you want to see what was actually injected
- Instinct injection or scratchpad filtering looks wrong and you need the rendered output
- A new hook was added and you want to confirm it composes into the spawn prompt
- A spawn failed silently (0 tool uses) and you want the prompt body for forensics

Turn it back off as soon as the investigation is done — there is no auto-off.

## Process

### Step 1: Parse the Argument

| Argument | Action |
|----------|--------|
| `on` | Set `CLAUDE_ENABLE_TRACE=1` for this session |
| `off` | Set `CLAUDE_ENABLE_TRACE=0` for this session |
| anything else | Print current state, do not change |

### Step 2: Apply

The skill exports the env var into the running session so the next `Agent`/`Skill` spawn picks it up. Persistence across sessions is not the goal — the default in `settings.json` env block is `0`, and that is the durable state.

For `on`:
```bash
export CLAUDE_ENABLE_TRACE=1
```

For `off`:
```bash
export CLAUDE_ENABLE_TRACE=0
```

### Step 3: Confirm and Locate Trace Output

After flipping, print:
```
[debug-trace] Tracing: enabled (CLAUDE_ENABLE_TRACE=1)
[debug-trace] Output dir: ~/.claude/metrics/{session-id}/trace/
[debug-trace] Retention: 7 days (pruned on SessionStart)
```
or:
```
[debug-trace] Tracing: disabled (CLAUDE_ENABLE_TRACE=0)
```

### Step 4: Privacy Reminder

When enabling, remind the user:
- Trace files are local-only and never committed (`metrics/` is gitignored)
- They contain the full rendered spawn prompt — instincts, session memory, scratchpad, agent memory, the lot
- Do not paste a trace file into a GitHub comment or external chat without redacting

## Phase Output

```
Verdict: TRACE_TOGGLED
State: enabled | disabled
Session: {session-id}
```

$ARGUMENTS
