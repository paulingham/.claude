#!/usr/bin/env python3
"""Thinking-defaults entry script. One stdin JSON in, decision + JSON out.

Reads the full hook payload from stdin, resolves the would-be defaults, and
emits two lines on stdout for the bash wrapper to consume:
  line 1: decision  -- "SKIP" (non-Agent or thinking already present) or "LOG"
  line 2: resolved  -- JSON dict {effort, display, source}
The `source` field names the layer that determined `effort`: "env", "explicit",
"role", or "default". The wrapper logs only when decision == "LOG" and exits 0
in either case.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from pipeline_state import read_active_state  # noqa: E402
from thinking_resolver import resolve  # noqa: E402


def _payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(payload):
    if payload.get("tool_name") != "Agent":
        return "SKIP"
    return "SKIP" if "thinking" in (payload.get("tool_input") or {}) else "LOG"


_BETA_HEADER_TOKEN = "effort-2025-11-24"


def _augment_wire_fields(resolved):
    """Add `beta_header` and `api_effort` to the resolved record.

    `beta_header` is OMITTED entirely (key not present) when the role
    layer downgrades the spawn to `effort=low` — these roles opt out of
    extended-thinking capability and emitting the header would request
    capability they explicitly decline. `api_effort` mirrors the
    resolved effort for downstream consumers.

    See `protocols/thinking-defaults.md` § Beta header for the rationale.
    """
    effort = resolved.get("effort")
    source = resolved.get("source")
    resolved["api_effort"] = effort
    role_disables_effort = effort == "low" and source == "role"
    if not role_disables_effort:
        resolved["beta_header"] = _BETA_HEADER_TOKEN
    return resolved


def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    resolved = resolve(tool_input=tool_input, env=os.environ, state=read_active_state())
    resolved = _augment_wire_fields(resolved)
    sys.stdout.write(f"{_decision(payload)}\n{json.dumps(resolved)}\n")


if __name__ == "__main__":
    main()
