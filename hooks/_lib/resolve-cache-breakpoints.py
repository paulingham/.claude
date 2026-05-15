#!/usr/bin/env python3
"""Prompt-cache breakpoint resolver. Stdin JSON in, 2-line stdout out.

Mirrors `_lib/resolve-thinking.py` shape:
  line 1: decision token  ("SKIP" non-Agent / "LOG" Agent)
  line 2: resolved payload JSON with 4 anchors

Anchor 1 (rules-core-tail) is `advisory` at v2.1.140 — we compute the
segment hash (SHA-256 of `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/rules/core.md`)
and the byte position. The hook layer logs but does not mutate
`tool_input.prompt`. Three other anchors are `deferred` with explicit reason
enums — see plan.md § Scope Decisions.
"""
import hashlib
import json
import os
import sys


_PERSONA_TAIL_ANCHOR = {
    "name": "persona-tail",
    "status": "advisory",
    "ttl": "1h",
    "reason": "promoted-slice-c-2026-05-15",
}

_DEFERRED_ANCHORS = [
    {"name": "protocol-tail", "status": "deferred",
     "reason": "protocol-splice-not-implemented"},
    {"name": "tool-result-tail", "status": "deferred",
     "reason": "outside-hook-surface-v2.1.140"},
]


def _config_dir() -> str:
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.environ.get("HOME", ""), ".claude")


def _rules_core_anchor() -> dict:
    path = os.path.join(_config_dir(), "rules", "core.md")
    try:
        data = open(path, "rb").read()
    except OSError:
        return {"name": "rules-core-tail", "status": "deferred",
                "reason": "rules-core-md-missing"}
    return {
        "name": "rules-core-tail",
        "status": "advisory",
        "ttl": "1h",
        "segment_hash": hashlib.sha256(data).hexdigest(),
        "byte_position": len(data),
    }


def _payload() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def _decision(payload: dict) -> str:
    return "LOG" if payload.get("tool_name") == "Agent" else "SKIP"


def main() -> int:
    payload = _payload()
    resolved = {
        "anchors": [_rules_core_anchor(), _PERSONA_TAIL_ANCHOR,
                    *_DEFERRED_ANCHORS],
        "cache_flag": True,
    }
    sys.stdout.write(f"{_decision(payload)}\n{json.dumps(resolved)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
