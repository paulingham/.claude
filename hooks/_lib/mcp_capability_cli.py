"""CLI entrypoint for mcp-capability-detect.sh.

WHY: hook calls this script; keep it thin — all logic lives in the lib.
Args: --input <raw mcp list text>  --session-id <sid>  --hook-root <path>
"""
import argparse
import json
import os
import sys
from pathlib import Path

def _parse_args(argv: list) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--input", default="")
    p.add_argument("--session-id", default="")
    p.add_argument("--hook-root", default="")
    return p.parse_args(argv)

def _data_root() -> str:
    return os.environ.get("CLAUDE_PLUGIN_DATA", os.path.expanduser("~/.claude"))

def _manifest_path() -> str:
    return str(Path(_data_root()) / "mcp-capability" / "manifest.json")

def _cap_map_path() -> Path:
    return Path(_data_root()) / "capability-map.json"

def _load_overrides() -> dict:
    cap_map = _cap_map_path()
    if not cap_map.exists():
        return {}
    try:
        return json.loads(cap_map.read_text()).get("overrides", {})
    except Exception:
        return {}

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
    if status in ("absent", "needs-auth"):
        ca.emit_once(cap_class, status, session_id, str(_marker_dir()), emit_fn=print)

def _emit_advisories(manifest: dict, session_id: str) -> None:
    _ensure_lib()
    caps = manifest.get("capabilities", {})
    for cap_class in ("design-source",):
        _advisory_for(cap_class, caps.get(cap_class), session_id)

def _run(args: argparse.Namespace) -> None:
    _ensure_lib()
    import mcp_capability as mc
    servers = mc.parse_mcp_list(args.input)
    rules = mc.load_seed_rules()
    manifest = mc.build_manifest(servers, rules, _load_overrides())
    mc.write_manifest(manifest, _manifest_path())
    _emit_advisories(manifest, args.session_id)

def main(argv: list | None = None) -> None:
    _run(_parse_args(argv or sys.argv[1:]))

if __name__ == "__main__":
    main()
