"""Capability advisory: distinct status messages, once-per-session emit, suppress.

WHY: needs-auth != absent — distinct advisory prevents "no MCP" confusion when
a server IS present but just needs re-authentication (plan.md § Distinct degrade
advisories). Emit once per session to avoid advisory spam across hooks.
"""
from __future__ import annotations

import json
from pathlib import Path

_NEEDS_AUTH = (
    "Design-source MCP '{server}' is connected but needs authentication"
    " — run `claude mcp` to re-auth/approve, then re-run."
    " Skipping design-brief ingest this run."
)
_ABSENT = (
    "No design-source MCP detected — connect a design MCP"
    " (e.g. DesignSync/Figma) or add an explicit tokens pointer"
    " to ~/.claude/capability-map.json. UI will use framework defaults this run."
)
_UNCLASSIFIED = (
    "MCP server '{server}' is connected but unclassified — if it provides"
    " design or tracker capability, add a mapping to ~/.claude/capability-map.json."
    " Ignored this run."
)


def advisory_text_for_status(status: str, server: str | None) -> str:
    """Return distinct advisory text for the given status and server name."""
    if status == "needs-auth":
        return _NEEDS_AUTH.format(server=server or "unknown")
    if status == "unclassified":
        return _UNCLASSIFIED.format(server=server or "unknown")
    return _ABSENT


def load_suppress_list(cap_map_path: str) -> list:
    """Load suppress:[<class>] from capability-map.json; empty list if absent."""
    path = Path(cap_map_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return data.get("suppress", [])


def _marker_path(capability: str, session_id: str, marker_dir: str) -> Path:
    safe_sid = session_id.replace("/", "_")
    return Path(marker_dir) / f"{capability}-{safe_sid}.marker"


def advisory_already_emitted(capability: str, session_id: str, marker_dir: str) -> bool:
    """Return True if advisory for this class was already emitted this session."""
    return _marker_path(capability, session_id, marker_dir).exists()


def emit_once(
    capability: str,
    status: str,
    session_id: str,
    marker_dir: str,
    *,
    server: str | None = None,
    emit_fn=print,
    suppress_list: list | None = None,
) -> bool:
    """Emit advisory once per session; return True if emitted, False otherwise."""
    if suppress_list and capability in suppress_list:
        return False
    if advisory_already_emitted(capability, session_id, marker_dir):
        return False
    text = advisory_text_for_status(status, server)
    emit_fn(text)
    _marker_path(capability, session_id, marker_dir).touch()
    return True
