#!/usr/bin/env python3
"""Thinking-defaults entry script. Reads stdin JSON, resolves, emits result.

Usage:
  echo '{"tool_input": {...}}' | python3 hooks/_lib/resolve-thinking.py
Outputs JSON: {"effort": "...", "display": "...", "source": "...",
               "missing": <bool>}  (missing=true if input had no thinking field)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from pipeline_state import read_active_state  # noqa: E402
from thinking_resolver import resolve  # noqa: E402


def _read_stdin():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def main():
    payload = _read_stdin()
    tool_input = payload.get("tool_input") or {}
    state = read_active_state()
    result = resolve(tool_input=tool_input, env=os.environ, state=state)
    result["missing"] = "thinking" not in tool_input
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
