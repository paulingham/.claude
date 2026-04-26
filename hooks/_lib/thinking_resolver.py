"""Pure precedence engine for resolving thinking defaults. No I/O."""


def _explicit(tool_input):
    return (tool_input or {}).get("thinking") or {}


def _env_override(env, key):
    return (env or {}).get(key)


def resolve(tool_input, env, state):
    explicit = _explicit(tool_input)
    effort = explicit.get("effort", "high")
    display = _env_override(env, "CLAUDE_THINKING_DISPLAY") or explicit.get("display", "omitted")
    return {"effort": effort, "display": display, "source": "default"}
