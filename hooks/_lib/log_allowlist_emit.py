"""Append a single JSONL line for tool-allowlist hook events.

Schema:
{"timestamp", "session_id", "agent_role", "requested_tools",
 "frontmatter_tools" (would_block only), "offending_tools",
 "action", "source"}

Field-level caps live in log_allowlist_entry. Session sanitisation lives
in log_allowlist_session. This module is the argv + file I/O wrapper.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from log_allowlist_entry import attach_frontmatter, build_entry  # noqa: E402
from log_allowlist_session import sanitize_session  # noqa: E402

# Backward-compat aliases for tests that import the underscore names
_entry = build_entry
_maybe_attach_frontmatter = attach_frontmatter
_sanitize_session = sanitize_session


def _parse_frontmatter(arg):
    return None if arg in ("null", "") else json.loads(arg)


def main():
    timestamp, input_json, resolved_json, out_path = sys.argv[1:5]
    fm_arg = sys.argv[5] if len(sys.argv) > 5 else "null"
    payload = json.loads(input_json or "{}")
    resolved = json.loads(resolved_json or "{}")
    entry = build_entry(timestamp, payload, resolved)
    attach_frontmatter(entry, resolved, _parse_frontmatter(fm_arg))
    with open(out_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    main()
