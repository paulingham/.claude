"""Pure precedence engine for resolving advisor-mode dispatch decisions. No I/O.

Path B precedent — see `rules/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `advisor`; the bash
wrapper is therefore log-only until the schema lands.
"""
from advisor_frontmatter import parse_frontmatter  # re-export

__all__ = ["parse_frontmatter", "resolve"]


def _solo(reason):
    return {"executor": None, "advisor": None, "fallback_reason": reason, "source": reason}


def _frontmatter_pairing(frontmatter):
    executor = (frontmatter or {}).get("executor")
    advisor = (frontmatter or {}).get("advisor")
    if not (executor and advisor):
        return None
    return {"executor": executor, "advisor": advisor,
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
    pairing = _frontmatter_pairing(frontmatter)
    return pairing if pairing else _solo("no-pairing-frontmatter")
