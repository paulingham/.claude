#!/usr/bin/env python3
"""Prompt-cache breakpoint resolver. Stdin JSON in, 2-line stdout out.

Mirrors `_lib/resolve-thinking.py` shape:
  line 1: decision token  ("SKIP" non-Agent / "LOG" Agent)
  line 2: resolved payload JSON with 4 anchors

Anchor 1 (rules-core-tail) is `advisory` at v2.1.140 — we compute the
segment hash (SHA-256 of rules/core.md) and the byte position. The hook
layer logs but does not mutate `tool_input.prompt`. Three other anchors
are `deferred` with explicit reason enums — see plan.md § Scope Decisions.

rules/core.md resolution precedence (plugin-install aware):
  CLAUDE_PLUGIN_ROOT > HARNESS_DATA > CLAUDE_CONFIG_DIR > $HOME/.claude
"""
import hashlib
import json
import os
import sys

from harness_paths import harness_data


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
    """Runtime-state base: HARNESS_DATA > harness_data() fallback."""
    return os.environ.get("HARNESS_DATA") or str(harness_data())


def _rules_core_path() -> "str | None":
    """Return first resolvable path for rules/core.md, or None.

    Precedence: CLAUDE_PLUGIN_ROOT > HARNESS_DATA > harness_data() fallback
    CLAUDE_PLUGIN_ROOT is checked first because in plugin-install mode the harness
    code (including rules/) lives under the plugin root, which differs from
    HARNESS_DATA (runtime state) and harness_data() (cold-start fallback).
    """
    candidates = [
        os.environ.get("CLAUDE_PLUGIN_ROOT"),
        _config_dir(),
    ]
    for base in candidates:
        if not base:
            continue
        path = os.path.join(base, "rules", "core.md")
        if os.path.isfile(path):
            return path
    return None


def _rules_core_anchor() -> dict:
    path = _rules_core_path()
    if path is None:
        return {"name": "rules-core-tail", "status": "deferred",
                "reason": "rules-core-md-missing"}
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
