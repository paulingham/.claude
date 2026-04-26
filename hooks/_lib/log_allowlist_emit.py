"""Build and append a single JSONL line for tool-allowlist hook events.

Schema:
{"timestamp", "session_id", "agent_role", "requested_tools",
 "frontmatter_tools" (would_block only), "offending_tools",
 "action", "source"}

Caps agent_role at 64 chars. Reads CLAUDE_SESSION_ID for session_id.
"""
import json
import os
import sys


def _entry(timestamp, payload, resolved):
    tool_input = payload.get("tool_input") or {}
    return {
        "timestamp": timestamp,
        "session_id": os.environ.get("CLAUDE_SESSION_ID", ""),
        "agent_role": tool_input.get("subagent_type", "")[:64],
        "requested_tools": tool_input.get("allowed_tools") or [],
        "offending_tools": resolved.get("offending_tools") or [],
        "action": resolved.get("action", ""),
        "source": "path-b-advisory",
    }


def _maybe_attach_frontmatter(entry, resolved, payload_tools):
    if resolved.get("action") == "would_block" and payload_tools is not None:
        entry["frontmatter_tools"] = payload_tools
    return entry


def main():
    timestamp, input_json, resolved_json, out_path = sys.argv[1:5]
    payload = json.loads(input_json or "{}")
    resolved = json.loads(resolved_json or "{}")
    entry = _entry(timestamp, payload, resolved)
    _maybe_attach_frontmatter(entry, resolved, payload.get("_frontmatter_tools"))
    with open(out_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry)[:1024] + "\n")


if __name__ == "__main__":
    main()
