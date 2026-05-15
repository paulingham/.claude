"""Pure precedence engine for resolving advisor-mode dispatch decisions. No I/O.

Path B precedent — see `rules/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `advisor`; the bash
wrapper is therefore log-only until the schema lands.
"""
from advisor_frontmatter import parse_frontmatter  # re-export

__all__ = [
    "parse_frontmatter",
    "resolve",
    "resolve_model_conditional",
    "advisor_none_to_python_none",
]


def _solo(reason):
    return {"executor": None, "advisor": None, "fallback_reason": reason, "source": reason}


def _env_disabled(env):
    return _solo("env-disabled") if (env or {}).get("CLAUDE_REVIEW_ADVISOR_DISABLED") == "1" else None


def _no_api_key(env):
    return _solo("no-api-key") if not (env or {}).get("ANTHROPIC_API_KEY") else None


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
