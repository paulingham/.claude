"""Pure precedence engine for resolving advisor-mode dispatch decisions. No I/O.

Path B precedent — see `protocols/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `advisor`; the bash
wrapper is therefore log-only until the schema lands.
"""
from advisor_frontmatter import parse_frontmatter  # re-export

__all__ = [
    "parse_frontmatter",
    "resolve",
    "resolve_model_conditional",
    "advisor_none_to_python_none",
    "route_model",
    "extract_router_signals",
]

# ---------------------------------------------------------------------------
# Router policy (Story 2)
# ---------------------------------------------------------------------------
# Pure: no I/O, no env reads, no subprocess.
# Mirrors purity convention of resolve_model_conditional above.
#
# Policy table (first match wins):
#   role in {architect, security-engineer}            -> expensive  (hard-locked)
#   prior_error_count >= 2                            -> expensive  (buy capability)
#   complexity_budget is not None and budget >= 10   -> expensive  (high-CB work)
#   graph_depth is not None and graph_depth >= 3     -> expensive  (deep recursion)
#   budget is not None and budget <= 4
#     and (graph_depth is None or graph_depth <= 1)
#     and prior_error_count == 0                     -> cheap      (shallow, clean)
#   otherwise                                        -> standard   (default arm)

_LOCKED_ROLES = frozenset({"architect", "security-engineer"})


def _is_locked_role(signals):
    return signals["role"] in _LOCKED_ROLES


def _is_deep(signals):
    depth = signals["graph_depth"]
    return depth is not None and depth >= 3


def _is_cheap_arm(signals):
    budget = signals["complexity_budget"]
    depth = signals["graph_depth"]
    errors = signals["prior_error_count"]
    if budget is None or budget > 4:
        return False
    if depth is not None and depth > 1:
        return False
    return errors == 0


def route_model(signals):
    """Return tier string 'cheap'|'standard'|'expensive' for a signals dict.

    signals must contain: role (str), complexity_budget (int|None),
    prior_error_count (int), graph_depth (int|None).
    Raises KeyError/TypeError/ValueError on malformed signals — no coercion.
    Pure; no I/O.
    """
    # Access all required keys up front — raises KeyError if any missing.
    role = signals["role"]
    budget = signals["complexity_budget"]
    errors = signals["prior_error_count"]
    depth = signals["graph_depth"]

    # Validate types for non-None values — raises TypeError/ValueError on bad input.
    if budget is not None and not isinstance(budget, int):
        raise TypeError(f"complexity_budget must be int or None, got {type(budget)!r}")
    if not isinstance(errors, int):
        raise TypeError(f"prior_error_count must be int, got {type(errors)!r}")
    if depth is not None and not isinstance(depth, int):
        raise TypeError(f"graph_depth must be int or None, got {type(depth)!r}")

    if _is_locked_role(signals):
        return "expensive"
    if errors >= 2:
        return "expensive"
    if budget is not None and budget >= 10:
        return "expensive"
    if _is_deep(signals):
        return "expensive"
    if _is_cheap_arm(signals):
        return "cheap"
    return "standard"


def extract_router_signals(role, graph_depth, complexity_budget, prior_error_count=0):
    """Assemble the router signals dict from already-parsed inputs.

    Pure: takes values already read by the caller (no env/I/O).
    graph_depth=0 is preserved as int 0 (distinct from None = unset/top-level).
    Returns a 4-key dict: {role, complexity_budget, prior_error_count, graph_depth}.
    """
    return {
        "role": role,
        "complexity_budget": complexity_budget,
        "prior_error_count": prior_error_count,
        "graph_depth": graph_depth,
    }


def _solo(reason):
    return {"executor": None, "advisor": None, "fallback_reason": reason, "source": reason}


def _env_disabled(env):
    disabled = (env or {}).get("CLAUDE_REVIEW_ADVISOR_DISABLED") == "1"
    return _solo("env-disabled") if disabled else None


def _no_api_key(env):
    has_key = bool((env or {}).get("ANTHROPIC_API_KEY"))
    return _solo("no-api-key") if not has_key else None


def _pairing(fm):
    return {"executor": fm["executor"], "advisor": fm["advisor"],
            "fallback_reason": "", "source": "frontmatter-pairing"}


def resolve(tool_input, env, frontmatter):
    """Resolve advisor pairing decision for an Agent spawn.

    Future-state: when the Agent input schema exposes `advisor`, the wrapper
    will inject this decision at PreToolUse time. Today the hook is log-only.
    The runtime fallback path `runtime-advisor-unavailable` is documented here
    but cannot be exercised today because the resolver runs PreToolUse,
    before any actual API call. The runtime fallback will live in the
    executor wrapper that dispatches the Sonnet+Opus-advisor pair.
    Returns dict with keys: executor, advisor, fallback_reason, source.
    """
    fm = frontmatter or {}
    if not (fm.get("executor") and fm.get("advisor")):
        return _solo("no-pairing-frontmatter")
    return _env_disabled(env) or _no_api_key(env) or _pairing(fm)


def _top_level_triple(fm):
    return {"model": fm.get("model"), "executor": fm.get("executor"),
            "advisor": fm.get("advisor"), "source": "no-conditional"}


def _arm(arm_dict, source):
    return {"model": arm_dict.get("model"), "executor": arm_dict.get("executor"),
            "advisor": arm_dict.get("advisor"), "source": source}


def _first_matching_rule(rules, budget):
    for rule in rules or []:
        budget_lt = (rule.get("when") or {}).get("budget_lt")
        if budget_lt is not None and budget < budget_lt:
            return _arm(rule, f"rule-match:budget_lt:{budget_lt}")
    return None


def resolve_model_conditional(frontmatter, budget):
    """Resolve model_conditional gate to {model, executor, advisor, source}.

    source in {"no-conditional", "no-budget", "rule-match:budget_lt:N", "default-arm"}.
    Pure; no I/O. See protocols/advisor-mode.md > model_conditional Schema.
    """
    fm = frontmatter or {}
    block = fm.get("model_conditional")
    if not block:
        return _top_level_triple(fm)
    default_arm = block.get("default") or {}
    if budget is None:
        return _arm(default_arm, "no-budget")
    matched = _first_matching_rule(block.get("rules"), budget)
    return matched or _arm(default_arm, "default-arm")


def advisor_none_to_python_none(advisor):
    """Translate the literal string 'none' to Python None for callers."""
    return None if advisor == "none" else advisor
