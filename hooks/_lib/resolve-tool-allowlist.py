#!/usr/bin/env python3
"""Tool-allowlist entry script. One stdin JSON in, decision + JSON out.

Reads the full hook payload from stdin, looks up the agent's frontmatter
tools by `subagent_type`, resolves the would-be allowlist decision, and
emits two lines on stdout for the bash wrapper to consume:
  line 1: decision  -- "SKIP" or "LOG"
  line 2: resolved  -- JSON dict {action, source, offending_tools}
The wrapper logs only when decision == "LOG" and exits 0 in either case.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from agent_tools_loader import load_agent_tools  # noqa: E402
from tool_allowlist_resolver import resolve  # noqa: E402


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(resolved):
    return "SKIP" if resolved["action"] == "skip" else "LOG"


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    tools = load_agent_tools(tool_input.get("subagent_type", ""))
    resolved = resolve(payload.get("tool_name"), tool_input, tools)
    sys.stdout.write(f"{_decision(resolved)}\n{json.dumps(resolved)}\n")


if __name__ == "__main__":
    main()
