"""Pure precedence engine for resolving advisor-mode dispatch decisions. No I/O.

Path B precedent — see `rules/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `advisor`; the bash
wrapper is therefore log-only until the schema lands.
"""
from advisor_frontmatter import parse_frontmatter  # re-export

__all__ = ["parse_frontmatter", "resolve"]


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
