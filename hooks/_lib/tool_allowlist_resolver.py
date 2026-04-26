"""Pure precedence engine for resolving per-agent tool allowlist decisions.

No I/O. Path B precedent — see `rules/thinking-defaults.md > ## Hook Behavior`.
The Agent input schema does not currently expose `allowed_tools`; the bash
wrapper is therefore log-only until the schema lands.

Returns dict with keys: action, source, offending_tools.
"""
from agent_path_validator import is_valid_subagent_type


def _skip(source):
    return {"action": "skip", "source": source, "offending_tools": []}


def resolve(tool_name, tool_input, frontmatter_tools):
    if tool_name != "Agent":
        return _skip("non-agent")
    subagent_type = (tool_input or {}).get("subagent_type", "")
    if not is_valid_subagent_type(subagent_type):
        return _skip("invalid-subagent-type")
    return _skip("non-agent")
