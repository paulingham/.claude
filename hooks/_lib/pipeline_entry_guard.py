"""Pipeline Entry Guard — pure decision core.

`decide(ctx: dict) -> dict` is the sole public entry point. No env reads,
no file I/O, no subprocess calls — all signal gathering happens in
pipeline_entry_guard_cli.py before this function is invoked.
"""
from __future__ import annotations

GATED_ROLES: frozenset = frozenset({
    "software-engineer",
    "frontend-engineer",
    "database-engineer",
    "infrastructure-engineer",
    "qa-engineer",
})


def _entry_signal(ctx: dict) -> str | None:
    """Return the first truthy pipeline-entry signal, or None."""
    if ctx.get("task_id"):
        return "task_id"
    if ctx.get("has_active_pipeline"):
        return "active_pipeline"
    if ctx.get("gear"):
        return "gear"
    return None


def decide(ctx: dict) -> dict:
    """Return the gate verdict dict for the given context.

    Short-circuit order:
    1. non-gated role  → allow
    2. disabled        → bypass
    3. task_id         → allow(task_id)
    4. active_pipeline → allow(active_pipeline)
    5. gear            → allow(gear)
    6. else            → block
    """
    role = ctx.get("role", "")
    if role not in GATED_ROLES:
        return {"action": "allow", "role": role, "signal": None,
                "reason": f"role '{role}' is not gated"}
    if ctx.get("disabled"):
        return {"action": "bypass", "role": role, "signal": None,
                "reason": "CLAUDE_DISABLE_PIPELINE_ENTRY_GUARD=1"}
    signal = _entry_signal(ctx)
    if signal:
        return {"action": "allow", "role": role, "signal": signal,
                "reason": f"pipeline-entry signal present: {signal}"}
    return {
        "action": "block",
        "role": role,
        "signal": None,
        "reason": (
            f"no pipeline-entry signal for gated role '{role}' — "
            "run /harness:intake or /harness:pipeline first"
        ),
    }
