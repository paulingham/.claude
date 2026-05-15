"""Role + state evaluation for thinking defaults. Pure functions.

Policy (PR #124 narrow-xhigh-promotion 2026-05-14): primary build/design
roles promote to xhigh on a stakes-bearing trigger, not unconditionally.
Each clause is inlined in `_is_xhigh()` with a per-role threshold. The
disjunctive (OR) gate fires on either a critical pipeline or a budget at
or above the role's threshold. One role (the security clause) retains its
existing conjunctive (AND) gate — distinct operator. See proposal at
`protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` for cost
rationale and rollback guidance.

The `_PROMOTE_TO_XHIGH` frozenset is retained as the empty set so the
snapshot test in `tests/test_thinking_defaults.py` continues to flag any
future re-population of the unconditional roster.

`_DOWNGRADE_TO_HIGH` / `_DOWNGRADE_TO_LOW` pin review/critic/database and
poll-loop roles whose iteration economics make xhigh wasteful; drift is
locked by `DowngradeListMatchesAgentFrontmatter`.
"""

# Empty after PR #124. Kept as the import surface for the snapshot test
# `PromoteToXhighListMatchesAgentFrontmatter` — a non-empty value here would
# surface immediately as a snapshot mismatch. Per-role promotion is now
# expressed inline in `_is_xhigh()` with explicit thresholds.
_PROMOTE_TO_XHIGH = frozenset()

# Review / critic / database roles that retain the high floor. Drift pinned
# by `DowngradeListMatchesAgentFrontmatter`.
_DOWNGRADE_TO_HIGH = frozenset({
    "code-reviewer", "qa-engineer", "product-reviewer",
    "patch-critic", "database-engineer", "security-engineer",
})

# planning-agent runs a long-poll loop on Haiku (slice-C demotion 2026-05)
# — xhigh per cycle is pure waste. Source: agents/planning-agent.md
# `model: haiku`. The effort downgrade is unchanged across the executor
# flip; only the model frontmatter moved.
_DOWNGRADE_TO_LOW = frozenset({"planning-agent"})


def _is_xhigh(role, critical, budget):
    if role == "architect":
        return critical or budget >= 6
    if role == "software-engineer":
        return critical or budget >= 7
    if role == "frontend-engineer":
        return critical or budget >= 7
    if role == "infrastructure-engineer":
        return critical or budget >= 7
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
