"""Pure precedence engine for resolving thinking defaults. No I/O."""

_EFFORTS = {"low", "medium", "high", "xhigh"}
_DISPLAYS = {"omitted", "text"}


def _explicit(tool_input):
    return (tool_input or {}).get("thinking") or {}


def _valid_env(env, key, allowed):
    value = (env or {}).get(key)
    return value if value in allowed else None


def _is_xhigh(role, critical, budget):
    if role == "architect" and (critical or budget >= 7):
        return True
    return role == "security-engineer" and critical and budget >= 7


def _is_best_of_n(name, budget):
    return name.startswith("boN-") and budget >= 7


def _role_effort(tool_input, state):
    name = (tool_input or {}).get("name", "")
    role = (tool_input or {}).get("subagent_type", "")
    critical, budget = (state or {}).get("critical", False), (state or {}).get("budget", 0)
    if _is_xhigh(role, critical, budget) or _is_best_of_n(name, budget):
        return "xhigh"
    return None


def _state_display(state):
    return "text" if (state or {}).get("debug_active") else None


def resolve(tool_input, env, state):
    explicit = _explicit(tool_input)
    role = _role_effort(tool_input, state)
    effort = _valid_env(env, "CLAUDE_THINKING_EFFORT", _EFFORTS) or explicit.get("effort") or role or "high"
    display = _valid_env(env, "CLAUDE_THINKING_DISPLAY", _DISPLAYS) or explicit.get("display") or _state_display(state) or "omitted"
    return {"effort": effort, "display": display, "source": "default"}
