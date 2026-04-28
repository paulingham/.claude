"""Time-bounded debug display resolver.

When debug-state is active, force display=text only if debug file age is
within DEBUG_DISPLAY_TTL_SECONDS. Beyond TTL, fall through to default omitted.
Continuation cycles (long-running debug sessions) avoid expensive thinking.
"""
DEBUG_DISPLAY_TTL_SECONDS = 1800


def _ttl(env):
    raw = (env or {}).get("CLAUDE_DEBUG_DISPLAY_TTL")
    try:
        return float(raw) if raw is not None else DEBUG_DISPLAY_TTL_SECONDS
    except (TypeError, ValueError):
        return DEBUG_DISPLAY_TTL_SECONDS


def debug_display(state, env, now):
    if not (state or {}).get("debug_active"):
        return None
    mtime = (state or {}).get("debug_mtime")
    if mtime is None:
        return "text"
    return "text" if (now - mtime) < _ttl(env) else None
