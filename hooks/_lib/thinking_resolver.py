"""Pure precedence engine for resolving thinking defaults. No I/O.

Returns {"effort", "display", "source"} where `source` names the layer that
determined the EFFORT value: "env", "explicit", "role", or "default".
Display layer may differ but is not separately reported.
"""
import time

from thinking_debug_display import debug_display
from thinking_role import role_effort

_EFFORTS = {"low", "medium", "high", "xhigh"}
_DISPLAYS = {"omitted", "text"}


def _explicit(tool_input):
    return (tool_input or {}).get("thinking") or {}


def _valid_env(env, key, allowed):
    value = (env or {}).get(key)
    return value if value in allowed else None


def _pick(layers, fallback):
    for source, value in layers:
        if value:
            return value, source
    return fallback, "default"


def resolve(tool_input, env, state, now=None):
    explicit = _explicit(tool_input)
    effort, source = _pick([
        ("env", _valid_env(env, "CLAUDE_THINKING_EFFORT", _EFFORTS)),
        ("explicit", explicit.get("effort")),
        ("role", role_effort(tool_input, state)),
    ], "xhigh")
    display, _ = _pick([
        ("env", _valid_env(env, "CLAUDE_THINKING_DISPLAY", _DISPLAYS)),
        ("explicit", explicit.get("display")),
        ("role", debug_display(state, env, now if now is not None else time.time())),
    ], "omitted")
    return {"effort": effort, "display": display, "source": source}
