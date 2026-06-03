#!/usr/bin/env python3
"""Instinct-injection entry script. One stdin JSON in, one JSONL line out.

Reads the Agent tool_input payload, resolves which learned-instincts apply,
and writes a forensic record to ~/.claude/metrics/{session}/instinct-injections.jsonl.
Always exit 0 (Path B advisory). The orchestrator-side caller is responsible
for actual prompt-string injection — see protocols/autonomous-intelligence.md.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from agent_parent_chain import load_expanded_instinct_categories  # noqa: E402
from agent_path_validator import is_valid_subagent_type  # noqa: E402
from instinct_env import resolve_top_n  # noqa: E402
from instinct_injector import effective_floor, resolve_for_agent  # noqa: E402
from instinct_loader import load_instincts  # noqa: E402
from resolve_instincts_helpers import count_kept, project_hash, read_payload, write_log  # noqa: E402


def _agent_input(payload):
    if payload.get("tool_name") != "Agent":
        return None
    sub = (payload.get("tool_input") or {}).get("subagent_type", "")
    return sub if is_valid_subagent_type(sub) else None


def _resolved(rendered, cats, kept, subagent_type=""):
    return {"count_kept": kept, "instinct_categories": cats,
            "min_confidence": effective_floor(subagent_type, os.environ),
            "top_n": resolve_top_n(5),
            "rendered_chars": len(rendered)}


def _handle_agent_spawn(payload, sub):
    cats = load_expanded_instinct_categories(sub) or []
    rendered = resolve_for_agent(sub, cats, load_instincts(project_hash()))
    kept = count_kept(rendered)
    write_log(payload, "logged", _resolved(rendered, cats, kept, sub))


def main():
    payload = read_payload()
    sub = _agent_input(payload)
    if sub:
        _handle_agent_spawn(payload, sub)


if __name__ == "__main__":
    main()
