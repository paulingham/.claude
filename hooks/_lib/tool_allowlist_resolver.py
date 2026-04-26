"""Pure precedence engine for resolving per-agent tool allowlist decisions.

No I/O. Path B precedent — see `rules/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `allowed_tools`; the bash
wrapper is therefore log-only until the schema lands.

Returns dict with keys: action, source, offending_tools.
"""
from agent_path_validator import is_valid_subagent_type


def _result(action, source, offending=()):
    return {"action": action, "source": source, "offending_tools": list(offending)}


def _preflight(tool_name, tool_input):
    if tool_name != "Agent":
        return _result("skip", "non-agent")
    if not is_valid_subagent_type((tool_input or {}).get("subagent_type", "")):
        return _result("skip", "invalid-subagent-type")
    return None


def _advisory(tool_input, frontmatter_tools):
    if frontmatter_tools is None:
        return _result("advisory", "no-tools-declared")
    if "allowed_tools" not in (tool_input or {}):
        return _result("advisory", "schema-absent")
    return None


def resolve(tool_name, tool_input, frontmatter_tools):
    return (_preflight(tool_name, tool_input)
            or _advisory(tool_input, frontmatter_tools)
            or _result("skip", "non-agent"))
