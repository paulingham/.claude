"""Role + state evaluation for thinking defaults. Pure functions.

Downgrade sets below pin the cost-mapped carve-outs: roles whose default
executor is Sonnet 4.6 (or whose iteration economics make xhigh wasteful)
must NOT inherit the xhigh fallback. Drift vs `agents/<role>.md` frontmatter
is locked in by the AC7 snapshot test in `tests/test_thinking_defaults.py`.
"""

# Sonnet executors per agents/<role>.md frontmatter:
#   code-reviewer     — model: opus,   executor: claude-sonnet-4-6 (advisor)
#   qa-engineer       — model: sonnet
#   product-reviewer  — model: sonnet
#   patch-critic      — model: sonnet, executor: claude-sonnet-4-6 (advisor)
#   database-engineer — model: sonnet
#   security-engineer — model: opus,   executor: claude-sonnet-4-6 (advisor)
_DOWNGRADE_TO_HIGH = frozenset({
    "code-reviewer", "qa-engineer", "product-reviewer",
    "patch-critic", "database-engineer", "security-engineer",
})

# planning-agent runs a long-poll loop on Sonnet — xhigh per cycle is
# pure waste. Source: agents/planning-agent.md `model: sonnet`.
_DOWNGRADE_TO_LOW = frozenset({"planning-agent"})


def _is_xhigh(role, critical, budget):
    if role == "architect" and (critical or budget >= 7):
        return True
    return role == "security-engineer" and critical and budget >= 7


def _is_best_of_n(name, budget):
    return name.startswith("boN-") and budget >= 7


def _role_downgrade(role):
    if role in _DOWNGRADE_TO_LOW:
        return "low"
    return "high" if role in _DOWNGRADE_TO_HIGH else None


def role_effort(tool_input, state):
    name = (tool_input or {}).get("name", "")
    role = (tool_input or {}).get("subagent_type", "")
    critical = (state or {}).get("critical", False)
    budget = (state or {}).get("budget", 0)
    if _is_xhigh(role, critical, budget) or _is_best_of_n(name, budget):
        return "xhigh"
    return _role_downgrade(role)
