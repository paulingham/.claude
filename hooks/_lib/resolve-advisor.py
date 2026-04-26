#!/usr/bin/env python3
"""Advisor-mode entry script. One stdin JSON in, decision + JSON out.

Reads the full hook payload from stdin, looks up the agent's frontmatter
by `subagent_type`, resolves the would-be advisor pairing, and emits two
lines on stdout for the bash wrapper to consume:
  line 1: decision  -- "SKIP" (non-Agent) or "LOG" (record what we WOULD inject)
  line 2: resolved  -- JSON dict {executor, advisor, fallback_reason, source}
The wrapper logs only when decision == "LOG" and exits 0 in either case.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from advisor_resolver import resolve  # noqa: E402
from agent_frontmatter_loader import load_agent_frontmatter  # noqa: E402


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(payload):
    return "SKIP" if payload.get("tool_name") != "Agent" else "LOG"


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    frontmatter = load_agent_frontmatter(tool_input.get("subagent_type", ""))
    resolved = resolve(tool_input=tool_input, env=os.environ, frontmatter=frontmatter)
    sys.stdout.write(f"{_decision(payload)}\n{json.dumps(resolved)}\n")


if __name__ == "__main__":
    main()
