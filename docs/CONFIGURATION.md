# Configuration

The harness's behaviour is tuned through env vars in `settings.json` (or a project's
`.claude/settings.json`). This page covers the knobs an engineer is most likely to reach for.

## Hook profiles

Set `CLAUDE_HOOK_PROFILE`:

- `minimal` — blocking hooks only (quality-gate, orchestrator-discipline)
- `standard` — all hooks (default)
- `strict` — all hooks (reserved for future stricter checks)

## Code-shape limits

The shape rules are cohesion-first; line counts are advisory smell signals with a generous
safety-net cap for clearly runaway output. Override per project in `settings.json` env or a
project `.claude/shape-overrides.json`:

- `CLAUDE_FILE_LINE_LIMIT` — hard file-length safety net (default: **300**; 150 is the soft warning)
- `CLAUDE_FUNCTION_LINE_LIMIT` — function-body length (default: **8**, advisory)

Per-glob overrides go in `.claude/shape-overrides.json`.

## Auto-extraction

Set `CLAUDE_AUTO_EXTRACT=true` to automatically extract modules when 3+ extraction signals
are detected during code review.

## Mechanical enforcement (hooks)

The hooks are the harness's guardrails — they enforce the iron laws so the rules don't
depend on the model remembering them. They run at three levels:

- **Hard block** — refuses the action (e.g. orchestrator editing source, PR without passing
  quality gate, file over the safety-net line cap).
- **Advisory** — surfaces a warning but lets the action through (cyclomatic complexity,
  function length, context-window usage).
- **Passive** — records data for cost/learning/governance without affecting the action.

The full hook registry (87 scripts, what each enforces and at what level) lives in
[`settings.json`](../settings.json) and is described per-hook in the hook files themselves.
Resource-bound caps (recursion depth, wall-clock limits), env overrides, and violation-log
schemas are in [`protocols/agent-protocol.md`](../protocols/agent-protocol.md) § Resource Bounds.

## Multi-language support

Hooks, shape checks, and the TDD guard support: **TypeScript, JavaScript, Ruby, Python, Go,
Java, Swift, Kotlin, C#**.
