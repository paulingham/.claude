"""CLI entrypoint for mcp-capability-detect.sh.

WHY: hook calls this script; keep it thin — all logic lives in the lib.
Args: --input <raw mcp list text>  --session-id <sid>  --hook-root <path>

Design-source consumer mode (orchestrator/pre-build callable):
  --consume-design-source --task-id <id> --state-dir <path>
  Reads the capability manifest, checks for design-source/explicit-pointer,
  calls select_adapter -> ingest -> write_design_brief.
  No mcp__* call needed for explicit-pointer (local file only).
  DesignSync/Figma paths are deferred (no-op with advisory message).
"""
import argparse
import json
import os
import sys
from pathlib import Path

_EXTERNAL_ADAPTERS = {"designsync", "figma"}

def _add_detect_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", default="")
    p.add_argument("--session-id", default="")
    p.add_argument("--hook-root", default="")

def _add_consume_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--consume-design-source", action="store_true", default=False)
    p.add_argument("--task-id", default="")
    p.add_argument("--state-dir", default="")

def _parse_args(argv: list) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    _add_detect_args(p)
    _add_consume_args(p)
    return p.parse_args(argv)

def _data_root() -> str:
    return os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude"))

def _manifest_path() -> str:
    return str(Path(_data_root()) / "mcp-capability" / "manifest.json")

def _cap_map_path() -> Path:
    return Path(_data_root()) / "capability-map.json"

def _read_overrides_file(cap_map: Path) -> dict:
    try:
        return json.loads(cap_map.read_text()).get("overrides", {})
    except Exception:
        return {}

def _load_overrides() -> dict:
    cap_map = _cap_map_path()
    return _read_overrides_file(cap_map) if cap_map.exists() else {}

def _marker_dir() -> Path:
    d = Path(_data_root()) / "mcp-capability" / "markers"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _ensure_lib() -> None:
    lib_dir = str(Path(__file__).parent)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

def _advisory_for(cap_class: str, entry: dict | None, session_id: str) -> None:
    import capability_advisory as ca
    status = entry["status"] if entry else "absent"
    server = entry.get("server") if entry else None
    if status in ("absent", "needs-auth"):
        ca.emit_once(cap_class, status, session_id, str(_marker_dir()), server=server, emit_fn=print)

def _emit_advisories(manifest: dict, session_id: str) -> None:
    _ensure_lib()
    caps = manifest.get("capabilities", {})
    for cap_class in ("design-source",):
        _advisory_for(cap_class, caps.get(cap_class), session_id)

def _read_manifest_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def _load_manifest() -> dict:
    path = Path(_manifest_path())
    return _read_manifest_file(path) if path.exists() else {}

def _design_cap_entry(manifest: dict) -> dict | None:
    return manifest.get("capabilities", {}).get("design-source")

def _noop(reason: str) -> int:
    print(f"[design-source] {reason}", flush=True)
    return 0

def _is_external_adapter(adapter_name: str) -> bool:
    return adapter_name in _EXTERNAL_ADAPTERS

def _write_brief(dsa, cap_entry: dict, task_id: str, state_dir: str) -> int:
    adapter = dsa.select_adapter(cap_entry)
    brief_data = adapter.ingest()
    # WHY: explicit-pointer is local/trusted — is_external=False (no injection boundary)
    written = dsa.write_design_brief(brief_data, task_id, state_dir, is_external=False)
    print(f"[design-source] brief written: {written}", flush=True)
    return 0

def _consume_explicit_pointer(cap_entry: dict, task_id: str, state_dir: str) -> int:
    if not cap_entry.get("tokens_path", ""):
        return _noop("explicit-pointer missing tokens_path; no-op")
    import design_source_adapter as dsa
    return _write_brief(dsa, cap_entry, task_id, state_dir)

def _route_adapter(cap_entry: dict, task_id: str, state_dir: str) -> int:
    adapter_name = cap_entry.get("adapter", "")
    if _is_external_adapter(adapter_name):
        # WHY: DesignSync/Figma need live MCP calls from agent runtime — not in pre-build hook
        return _noop(f"adapter={adapter_name!r} is deferred (requires live MCP); no-op")
    if adapter_name != "explicit-pointer":
        return _noop(f"unknown adapter={adapter_name!r}; no-op")
    return _consume_explicit_pointer(cap_entry, task_id, state_dir)

def _consume_design_source(task_id: str, state_dir: str) -> int:
    """Ingest design-source (explicit-pointer only); write brief; deferred for MCP adapters."""
    _ensure_lib()
    cap_entry = _design_cap_entry(_load_manifest())
    if cap_entry is None:
        return _noop("no design-source capability in manifest — no-op")
    return _route_adapter(cap_entry, task_id, state_dir)

def _build_manifest(args: argparse.Namespace) -> dict:
    import mcp_capability as mc
    servers = mc.parse_mcp_list(args.input)
    rules = mc.load_seed_rules()
    return mc.build_manifest(servers, rules, _load_overrides())

def _run(args: argparse.Namespace) -> None:
    _ensure_lib()
    import mcp_capability as mc
    manifest = _build_manifest(args)
    mc.write_manifest(manifest, _manifest_path())
    _emit_advisories(manifest, args.session_id)

def main(argv: list | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.consume_design_source:
        return _consume_design_source(args.task_id, args.state_dir)
    _run(args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
