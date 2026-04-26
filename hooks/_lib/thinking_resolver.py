"""Pure precedence engine for resolving thinking defaults. No I/O."""

_EFFORTS = {"low", "medium", "high", "xhigh"}
_DISPLAYS = {"omitted", "text"}


def _explicit(tool_input):
    return (tool_input or {}).get("thinking") or {}


def _valid_env(env, key, allowed):
    value = (env or {}).get(key)
    return value if value in allowed else None


def resolve(tool_input, env, state):
    explicit = _explicit(tool_input)
    effort = _valid_env(env, "CLAUDE_THINKING_EFFORT", _EFFORTS) or explicit.get("effort", "high")
    display = _valid_env(env, "CLAUDE_THINKING_DISPLAY", _DISPLAYS) or explicit.get("display", "omitted")
    return {"effort": effort, "display": display, "source": "default"}
