"""Capture-path resolver — pure decision logic + scratchpad warning helper.

Node-side capture (a11y_capture.js / a11y_probe.js) is the production
path. This Python module mirrors the same decision tree so:

- tests can probe the resolution logic without spawning Node
- design-qc's Step 6.25 has a deterministic Python helper for writing
  the scratchpad warning when capture fails

Decision tree:
  1. mcp_probe(): if it raises -> jump to library
                  if it returns ok -> use mcp_capture
  2. mcp_capture(): if it raises -> jump to library
                    if it returns ok -> captured=true, capture_path=mcp
  3. library_capture(): if it raises -> captured=false, reason=mcp-unavailable
                        if it returns ok -> captured=true, capture_path=library
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


def resolve_capture(
    *,
    mcp_probe: Callable,
    mcp_capture: Callable,
    library_capture: Callable,
) -> dict:
    """Decide capture path. All three callables are dependency-injected.

    Returns: `{captured, capture_path, reason}`. `reason` is None when
    captured.
    """
    if _try(mcp_probe) and _try(mcp_capture):
        return _ok("mcp")
    if _try(library_capture):
        return _ok("library")
    return {"captured": False, "capture_path": None,
            "reason": "mcp-unavailable"}


def write_warning(scratchpad_path: str | Path, *, reason: str) -> None:
    """Append a scratchpad warning (YAML frontmatter + body)."""
    body = (
        "---\n"
        "category: warning\n"
        "---\n"
        f"\nA11y capture unavailable: {reason}.\n"
    )
    p = Path(scratchpad_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def _try(callable_) -> bool:
    try:
        result = callable_()
    except Exception:
        return False
    if isinstance(result, dict):
        return bool(result.get("ok", True))
    return True


def _ok(capture_path: str) -> dict:
    return {"captured": True, "capture_path": capture_path, "reason": None}
