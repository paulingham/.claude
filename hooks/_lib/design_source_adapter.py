"""Design-source adapters: ExplicitPointer, DesignSync, Figma (deferred).

WHY: s2 consumer reads capability-manifest and writes a flat design-brief
to pipeline-state/{task-id}-design-brief.md (frontend-engineer.md:136).
Figma adapter is a deferred slot — raises NotImplementedError until s3.
"""
from __future__ import annotations

import json
from pathlib import Path


class ExplicitPointerAdapter:
    """Reads a local tokens JSON file and returns it as the brief dict."""

    def __init__(self, tokens_path: str) -> None:
        self._path = Path(tokens_path)

    def ingest(self) -> dict:
        return json.loads(self._path.read_text())


class DesignSyncAdapter:
    """Calls DesignSync MCP tools and returns aggregated brief dict."""

    def __init__(self, project_id: str, call_tool_fn) -> None:
        self._project_id = project_id
        self._call = call_tool_fn

    def ingest(self) -> dict:
        components = self._call("list_components", {"project_id": self._project_id})
        variables = self._call("get_variables", {"project_id": self._project_id})
        return {"components": components, "variables": variables}


class FigmaAdapter:
    """Deferred slot — raises NotImplementedError until s3 ships."""

    def ingest(self) -> dict:
        # WHY: Figma adapter is a deferred slot (plan.md § AC9 DEFERRED-EVIDENCE-GAP).
        # Real Figma MCP pull unverified; not silently green per LSP #210 precedent.
        raise NotImplementedError("FigmaAdapter is a deferred slot (s3); not yet implemented.")


def _adapter_explicit(entry: dict) -> ExplicitPointerAdapter:
    return ExplicitPointerAdapter(entry.get("tokens_path", ""))


def _adapter_designsync(entry: dict) -> DesignSyncAdapter:
    call_fn = entry.get("call_tool_fn", lambda n, p: {})
    return DesignSyncAdapter(entry.get("project_id", ""), call_fn)


_HINT_MAP = {
    "figma": lambda e: FigmaAdapter(),
    "explicit-pointer": _adapter_explicit,
}


def select_adapter(capability_entry: dict) -> object:
    """Select the correct adapter from a capability entry's adapter_hint."""
    hint = capability_entry.get("adapter_hint", "")
    factory = _HINT_MAP.get(hint, _adapter_designsync)
    return factory(capability_entry)


def _render_section(key: str, value: object) -> list:
    return [f"## {key}", "", f"```json\n{json.dumps(value, indent=2)}\n```", ""]


def _brief_header() -> list:
    return ["# Design Brief", ""]


def render_design_brief(brief_data: dict) -> str:
    """Render brief dict to markdown string."""
    lines = _brief_header()
    for key, value in brief_data.items():
        lines.extend(_render_section(key, value))
    return "\n".join(lines)


def write_design_brief(brief_data: dict, task_id: str, state_dir: str) -> str:
    """Write flat pipeline-state/{task-id}-design-brief.md; return written path."""
    # WHY: flat path (not subdir) matches frontend-engineer.md:136 reader contract.
    path = Path(state_dir) / f"{task_id}-design-brief.md"
    path.write_text(render_design_brief(brief_data))
    return str(path)
