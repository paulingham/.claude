"""Role + state evaluation for thinking defaults. Pure functions.

Two role sets pin the policy after the May 2026 Opus 4.7 adaptive-thinking
floor change:

1. `_PROMOTE_TO_XHIGH` — primary build/design roles unconditionally elevated
   to xhigh. Apr 23 2026 cost/quality data captured the promotion-on-trigger
   lift; adaptive thinking changed the cost floor, so the gate is removed
   for these roles.
2. `_DOWNGRADE_TO_HIGH` / `_DOWNGRADE_TO_LOW` — review/critic/database/
   poll-loop roles whose iteration economics make xhigh wasteful.

Drift vs `agents/<role>.md` frontmatter is locked by snapshot tests
(`PromoteToXhighListMatchesAgentFrontmatter`,
`DowngradeListMatchesAgentFrontmatter`) in `tests/test_thinking_defaults.py`.
"""

# Build/design roles unconditionally promoted to xhigh per May 2026 policy.
# These four short-circuit `_is_xhigh()` regardless of `critical`/`budget`,
# overriding the historical conditional architect gate.
_PROMOTE_TO_XHIGH = frozenset({
    "architect", "software-engineer",
    "frontend-engineer", "infrastructure-engineer",
})

# Review / critic / database roles that retain the high floor. SE+FE were
# removed in May 2026 — they now ride `_PROMOTE_TO_XHIGH` instead. Drift
# pinned by `DowngradeListMatchesAgentFrontmatter`.
_DOWNGRADE_TO_HIGH = frozenset({
    "code-reviewer", "qa-engineer", "product-reviewer",
    "patch-critic", "database-engineer", "security-engineer",
})

# planning-agent runs a long-poll loop on Sonnet — xhigh per cycle is
# pure waste. Source: agents/planning-agent.md `model: sonnet`.
_DOWNGRADE_TO_LOW = frozenset({"planning-agent"})


def _is_xhigh(role, critical, budget):
    if role in _PROMOTE_TO_XHIGH:
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
