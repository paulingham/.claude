"""Role + state evaluation for thinking defaults. Pure functions."""


def _is_xhigh(role, critical, budget):
    if role == "architect" and (critical or budget >= 7):
        return True
    return role == "security-engineer" and critical and budget >= 7


def _is_best_of_n(name, budget):
    return name.startswith("boN-") and budget >= 7


def role_effort(tool_input, state):
    name = (tool_input or {}).get("name", "")
    role = (tool_input or {}).get("subagent_type", "")
    critical, budget = (state or {}).get("critical", False), (state or {}).get("budget", 0)
    if _is_xhigh(role, critical, budget) or _is_best_of_n(name, budget):
        return "xhigh"
    return None


def state_display(state):
    return "text" if (state or {}).get("debug_active") else None
