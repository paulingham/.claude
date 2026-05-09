#!/usr/bin/env python3
"""Mode-token-validator entry script. One stdin JSON in, decision + JSON out.

Reads the full hook payload from stdin, extracts the spawn prompt for a
patch-critic Agent call, runs the mode-token classifier, and emits two
lines on stdout:
  line 1: decision  -- "SKIP" (non-Agent / non-patch-critic / single-mode)
                       or "LOG" (mode-ambiguous; emit forensic JSONL)
  line 2: resolved  -- JSON dict {mode, status, tokens}

The bash wrapper (`hooks/pre-agent-advisor.sh`) logs only when
decision == "LOG" and exits 0 in either case (Path-B advisory).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mode_token_validator import classify_mode  # noqa: E402


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(payload, classification):
    if payload.get("tool_name") != "Agent":
        return "SKIP"
    if (payload.get("tool_input") or {}).get("subagent_type") != "patch-critic":
        return "SKIP"
    return "LOG" if classification.get("status") == "MODE_AMBIGUOUS" else "SKIP"


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    prompt = tool_input.get("prompt", "") or ""
    resolved = classify_mode(prompt)
    sys.stdout.write(f"{_decision(payload, resolved)}\n{json.dumps(resolved)}\n")


if __name__ == "__main__":
    main()
