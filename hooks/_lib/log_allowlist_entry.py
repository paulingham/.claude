"""Construct the dict-shaped allowlist log entry with field-level caps.

Caps are applied BEFORE serialisation so the resulting JSON line is
naturally bounded and always syntactically valid (vs the previous
post-serialisation byte slice which produced malformed JSON).
"""
import os

from log_allowlist_session import sanitize_session

_FIELD_CAP = 20
_STRING_CAP = 64


def build_entry(timestamp, payload, resolved):
    tool_input = payload.get("tool_input") or {}
    return {
        "timestamp": timestamp,
        "session_id": sanitize_session(os.environ.get("CLAUDE_SESSION_ID", "")),
        "agent_role": tool_input.get("subagent_type", "")[:_STRING_CAP],
        "requested_tools": (tool_input.get("allowed_tools") or [])[:_FIELD_CAP],
        "offending_tools": (resolved.get("offending_tools") or [])[:_FIELD_CAP],
        "action": resolved.get("action", ""),
        "source": "path-b-advisory",
    }


def attach_frontmatter(entry, resolved, frontmatter_tools):
    if resolved.get("action") == "would_block" and frontmatter_tools is not None:
        entry["frontmatter_tools"] = frontmatter_tools[:_FIELD_CAP]
    return entry
