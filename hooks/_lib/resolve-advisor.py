#!/usr/bin/env python3
"""Advisor-mode entry script. One stdin JSON in, decision + JSON out.

Reads the full hook payload from stdin, looks up the agent's frontmatter
by `subagent_type`, resolves the would-be advisor pairing, and emits three
lines on stdout for the bash wrapper to consume:
  line 1: decision      -- "SKIP" (non-Agent) or "LOG" (record would-be pairing)
  line 2: resolved      -- JSON dict {executor, advisor, fallback_reason, source}
  line 3: binding_output -- hookSpecificOutput JSON when model binding fires, else ""
The wrapper logs only when decision == "LOG" and exits 0 in either case.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from advisor_resolver import resolve, resolve_model_conditional  # noqa: E402
from agent_frontmatter_loader import load_agent_frontmatter  # noqa: E402
from model_binding import should_emit_model, build_hook_output  # noqa: E402
from pipeline_state import read_active_state  # noqa: E402


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(payload):
    return "SKIP" if payload.get("tool_name") != "Agent" else "LOG"


def _binding_output(decision, frontmatter, budget):
    """Compute hookSpecificOutput JSON or empty string for line 3."""
    if decision != "LOG":
        return ""
    mc = resolve_model_conditional(frontmatter, budget)
    if should_emit_model(mc):
        return build_hook_output(mc["model"])
    return ""


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    frontmatter = load_agent_frontmatter(tool_input.get("subagent_type", ""))
    resolved = resolve(tool_input=tool_input, env=os.environ, frontmatter=frontmatter)
    decision = _decision(payload)
    state = read_active_state()
    budget = state.get("budget") or None  # coerce 0 to None (indistinguishable from unset)
    binding = _binding_output(decision, frontmatter, budget)
    sys.stdout.write(f"{decision}\n{json.dumps(resolved)}\n{binding}\n")


if __name__ == "__main__":
    main()
