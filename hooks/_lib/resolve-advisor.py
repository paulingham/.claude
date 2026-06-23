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
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from advisor_resolver import (  # noqa: E402
    resolve, resolve_model_conditional, route_model, extract_router_signals,
)
from agent_frontmatter_loader import load_agent_frontmatter  # noqa: E402
from model_binding import should_emit_model, build_hook_output  # noqa: E402
from pipeline_state import active_pipeline_path, read_active_state  # noqa: E402


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


def _router_mode(raw: str):
    # WHY: pre-extracted string; os.environ never flows to stdout sink.
    # Returns 'off', 'shadow', or 'active'; fail-closed to 'off'.
    if raw in ("shadow", "active"):
        return raw
    return "off"


def _graph_depth(raw: str):
    # WHY: pre-extracted string; os.environ never flows to stdout sink.
    # '0' -> 0 (int, distinct from None = unset); non-numeric -> None.
    if raw and raw.isdigit():
        return int(raw)
    return None


def _intake_budget():
    """Read complexity_budget from the active pipeline's intake.md.

    Mirrors cost-helpers.sh:74-94 bash logic in Python.
    Delegates active-pipeline resolution to active_pipeline_path() so the
    router and read_active_state share one selection code path by construction.
    Returns int or None (never raises — budget absence is not an error).
    """
    try:
        pipeline_path = active_pipeline_path()
        if pipeline_path is None:
            return None
        intake_path = _resolve_intake_path(pipeline_path)
        if not intake_path.is_file():
            return None
        return _parse_budget_from_intake(intake_path)
    except Exception:  # noqa: BLE001
        return None


def _resolve_intake_path(pipeline_path):
    """Resolve sibling intake.md from a pipeline path (new or legacy layout)."""
    name = pipeline_path.name
    if name == "pipeline.md":
        return pipeline_path.parent / "intake.md"
    # Legacy: {task-id}-pipeline.md -> {task-id}-intake.md
    base = name[: -len("-pipeline.md")] if name.endswith("-pipeline.md") else name
    return pipeline_path.parent / f"{base}-intake.md"


def _parse_budget_from_intake(intake_path):
    """Extract first integer from complexity_budget flat or nested total: line."""
    try:
        text = intake_path.read_text()
        # Match the whole line so multi-digit numbers are captured.
        # Flat: complexity_budget: <digits>
        # Nested: <spaces>total: <digits>
        pattern = re.compile(
            r'^(complexity_budget:|[^\S\r\n]*total:)[^\S\r\n]*([0-9]+)',
            re.MULTILINE)
        match = pattern.search(text)
        if match:
            return int(match.group(2))
        return None
    except Exception:  # noqa: BLE001
        return None


def _try_route(role, depth_raw, router_raw):
    if _router_mode(router_raw) == "off":
        return None
    try:
        return route_model(extract_router_signals(
            role=role, graph_depth=_graph_depth(depth_raw),
            complexity_budget=_intake_budget(), prior_error_count=0))
    except Exception:  # noqa: BLE001
        return "error"
def _attach_router_decision(resolved, tool_input, router_raw, depth_raw):
    role = tool_input.get("subagent_type") or ""
    tier = _try_route(role, depth_raw, router_raw)
    if tier is not None:
        resolved["router_decision"] = tier
def _env_raws():
    # WHY: isolates os.environ reads; returned plain strings never taint resolved.
    return (os.environ.get("CLAUDE_MODEL_ROUTER", ""),
            os.environ.get("CLAUDE_SUBAGENT_DEPTH", ""))
def main():
    payload = _payload()
    tool_input = payload.get("tool_input") or {}
    frontmatter = load_agent_frontmatter(tool_input.get("subagent_type", ""))
    resolved = resolve(tool_input=tool_input,
        advisor_disabled=os.environ.get("CLAUDE_REVIEW_ADVISOR_DISABLED") == "1",
        has_api_key=bool(os.environ.get("ANTHROPIC_API_KEY")),
        frontmatter=frontmatter)
    decision = _decision(payload)
    binding = _binding_output(decision, frontmatter,
        read_active_state().get("budget") or None)
    if decision == "LOG":
        _attach_router_decision(resolved, tool_input, *_env_raws())
    sys.stdout.write(f"{decision}\n{json.dumps(resolved)}\n{binding}\n")


if __name__ == "__main__":
    main()
