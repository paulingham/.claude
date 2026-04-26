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
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from advisor_resolver import parse_frontmatter, resolve  # noqa: E402

_AGENTS_DIR = Path(os.environ.get("CLAUDE_AGENTS_DIR") or
                   Path.home() / ".claude" / "agents")


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _agent_frontmatter(subagent_type):
    if not subagent_type:
        return {}
    path = _AGENTS_DIR / f"{subagent_type}.md"
    return parse_frontmatter(path.read_text()) if path.exists() else {}


def _decision(payload):
    return "SKIP" if payload.get("tool_name") != "Agent" else "LOG"


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    frontmatter = _agent_frontmatter(tool_input.get("subagent_type", ""))
    resolved = resolve(tool_input=tool_input, env=os.environ, frontmatter=frontmatter)
    sys.stdout.write(f"{_decision(payload)}\n{json.dumps(resolved)}\n")


if __name__ == "__main__":
    main()
