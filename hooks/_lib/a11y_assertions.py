"""Pure-function a11y assertion engine for the dual-output design-qc rubric.

Two public surfaces:

- `evaluate(snapshot, denylist) -> [findings]` — pure, no I/O. Walks the
  snapshot's tree once (DFS pre-order) and records findings for assertions
  A1..A6.
- `run(index_path, project_root=None) -> {verdict, findings, reason?}` —
  the I/O wrapper consumed by patch-critic. Reads index.json, applies
  schema-version + capture-state SKIP semantics, then dispatches every
  captured per-route snapshot to `evaluate` and aggregates findings.

The boundary between Node (capture) and Python (assertions) is the JSON
file on disk; this module is the Python side.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

INDEX_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1

# Default A6 anti-pattern names (case-insensitive, lower-cased).
DEFAULT_A6_DENYLIST = [
    "click here",
    "here",
    "link",
    "button",
    "read more",
    "more",
    "...",
]

# Roles that are interactive form controls (subject to A3).
FORM_CONTROL_ROLES = frozenset({
    "textbox", "combobox", "checkbox", "radio", "switch",
    "slider", "spinbutton", "listbox",
})


# ---------- evaluate (pure) ----------

def evaluate(snapshot: dict, denylist: list[str]) -> list[dict]:
    """Run all assertions on snapshot. Pure; no I/O, no globals.

    Returns a list of finding dicts. Empty list = clean.
    """
    tree = snapshot.get("tree")
    if tree is None:
        return []
    route = snapshot.get("route")
    viewport = snapshot.get("viewport")
    visitor = _Visitor(route, viewport, list(denylist))
    visitor.walk(tree, ancestors=[], path="tree")
    visitor.check_heading_order()
    return visitor.findings


def effective_a6_denylist(default: list[str], overrides: dict) -> list[str]:
    """Compose effective A6 denylist from default + overrides dict.

    Overrides shape: `{a6_denylist_additions: [...], a6_denylist_removals: [...]}`
    Both fields are optional. Names are normalised to lower-cased + trimmed.
    """
    additions = [_norm(s) for s in overrides.get("a6_denylist_additions", [])]
    removals = {_norm(s) for s in overrides.get("a6_denylist_removals", [])}
    base = [n for n in default if n not in removals]
    for a in additions:
        if a and a not in base:
            base.append(a)
    return base


def _norm(s: str) -> str:
    return (s or "").strip().lower()


class _Visitor:
    """Single DFS pre-order pass; records findings + heading order for A5."""

    def __init__(self, route, viewport, denylist):
        self.route = route
        self.viewport = viewport
        self.denylist = denylist
        self.findings: list[dict] = []
        self.headings: list[tuple[dict, str, list[dict]]] = []  # (node, path, ancestors)

    # --- traversal ---

    def walk(self, node: dict, ancestors: list[dict], path: str) -> None:
        self._check_a1(node, ancestors, path)
        self._check_a2(node, ancestors, path)
        self._check_a3(node, ancestors, path)
        self._check_a4(node, ancestors, path)
        self._record_heading(node, ancestors, path)
        self._check_a6(node, ancestors, path)
        self._descend(node, ancestors, path)

    def _descend(self, node, ancestors, path):
        for i, child in enumerate(node.get("children", []) or []):
            self.walk(child, ancestors + [node], f"{path}.children[{i}]")

    # --- per-assertion checks ---

    def _check_a1(self, node, ancestors, path):
        if not node.get("interactive"):
            return
        if _aria_hidden(node):  # A4 covers hidden+interactive
            return
        if (node.get("name") or "").strip() == "":
            self._add(node, ancestors, path, "A1")

    def _check_a2(self, node, ancestors, path):
        if node.get("tag") != "img":
            return
        if (node.get("role") or "") == "presentation":
            return
        if (node.get("name") or "") == "":
            self._add(node, ancestors, path, "A2")

    def _check_a3(self, node, ancestors, path):
        if not node.get("interactive"):
            return
        if _aria_hidden(node):  # A4 covers hidden+interactive
            return
        if (node.get("role") or "") not in FORM_CONTROL_ROLES:
            return
        if (node.get("name") or "").strip() == "":
            self._add(node, ancestors, path, "A3")

    def _check_a4(self, node, ancestors, path):
        if not node.get("interactive"):
            return
        if _aria_hidden(node):
            self._add(node, ancestors, path, "A4")

    def _record_heading(self, node, ancestors, path):
        if (node.get("role") or "") == "heading":
            self.headings.append((node, path, list(ancestors)))

    def _check_a6(self, node, ancestors, path):
        if (node.get("role") or "") not in {"button", "link"}:
            return
        name = _norm(node.get("name") or "")
        if not name:
            return
        if name in self.denylist:
            self._add(node, ancestors, path, "A6")

    def check_heading_order(self):
        """A5 — DFS-ordered headings; flag downward skips of >1 only."""
        prev_level = None
        prev_path = None
        for node, path, ancestors in self.headings:
            level = (node.get("aria") or {}).get("level")
            if not isinstance(level, int):
                prev_level = level
                prev_path = path
                continue
            if isinstance(prev_level, int) and level - prev_level > 1:
                self._add(node, ancestors, path, "A5")
            prev_level = level
            prev_path = path

    # --- finding factory ---

    def _add(self, node, ancestors, path, assertion_id):
        self.findings.append({
            "assertion_id": assertion_id,
            "role": node.get("role") or "",
            "name": node.get("name") or "",
            "path_in_tree": path,
            "breadcrumb": _breadcrumb(ancestors, node),
            "route": self.route,
            "viewport": self.viewport,
        })


def _aria_hidden(node: dict) -> bool:
    aria = node.get("aria") or {}
    return bool(aria.get("hidden"))


def _breadcrumb(ancestors: list[dict], node: dict) -> str:
    parts = [_label(a) for a in ancestors]
    parts.append(_label(node))
    return " > ".join(parts)


def _label(node: dict) -> str:
    name = (node.get("name") or "").strip()
    if name:
        return name
    return f"<{node.get('role') or node.get('tag') or 'node'}>"


# ---------- run (I/O wrapper) ----------

def run(index_path: str, project_root: str | None = None) -> dict:
    """Read index.json, dispatch evaluate per snapshot, aggregate verdict."""
    payload = _read_index(index_path)
    if payload is None:
        return _skip("index-absent")

    schema = payload.get("schema_version")
    if schema != INDEX_SCHEMA_VERSION:
        return {"verdict": "SKIP", "reason": "schema-incompatible",
                "expected": INDEX_SCHEMA_VERSION, "found": schema,
                "findings": []}

    a11y_global = payload.get("a11y_global") or {}
    if not a11y_global.get("captured"):
        reason = a11y_global.get("reason") or "uncaptured"
        return _skip(reason)

    denylist = _resolve_denylist(project_root)
    findings, skipped = _evaluate_routes(payload.get("routes", []), denylist)

    verdict = "FAIL" if findings else "PASS"
    return {"verdict": verdict, "findings": findings,
            "skipped_routes": skipped}


def _evaluate_routes(routes, denylist):
    findings: list[dict] = []
    skipped: list[dict] = []
    for route_entry in routes:
        a11y = route_entry.get("a11y") or {}
        if not a11y.get("captured"):
            skipped.append({"route": route_entry.get("route"),
                            "reason": a11y.get("reason") or "capture-error"})
            continue
        for snap in a11y.get("snapshots", []) or []:
            findings.extend(_evaluate_snapshot_at(snap.get("path"), denylist))
    return findings, skipped


def _evaluate_snapshot_at(path: str | None, denylist: list[str]) -> list[dict]:
    if not path:
        return []
    try:
        snap = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if snap.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return []
    return evaluate(snap, denylist)


def _read_index(index_path: str) -> dict | None:
    p = Path(index_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _skip(reason: str) -> dict:
    return {"verdict": "SKIP", "reason": reason, "findings": []}


def _resolve_denylist(project_root: str | None) -> list[str]:
    if not project_root:
        return list(DEFAULT_A6_DENYLIST)
    overrides_path = Path(project_root) / ".claude" / "a11y-overrides.json"
    if not overrides_path.exists():
        return list(DEFAULT_A6_DENYLIST)
    try:
        overrides = json.loads(overrides_path.read_text())
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"[a11y_assertions] malformed overrides at {overrides_path}: "
            f"{exc.msg}; falling back to default denylist\n")
        return list(DEFAULT_A6_DENYLIST)
    return effective_a6_denylist(DEFAULT_A6_DENYLIST, overrides)
