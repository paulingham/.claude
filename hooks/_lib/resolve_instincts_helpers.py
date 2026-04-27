"""Helpers for resolve-instincts.py (Wave 4-M Slice 3)."""
import json
import os
import subprocess
import sys
from pathlib import Path


def read_payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def project_hash():
    script = Path(__file__).parent / "project-hash.sh"
    cmd = f'source "{script}" && _project_hash --fallback "local"'
    try:
        out = subprocess.check_output(["bash", "-c", cmd], stderr=subprocess.DEVNULL, timeout=3)
        return (out.decode().strip() or "local")
    except Exception:
        return "local"


def count_kept(rendered):
    return 0 if not rendered else sum(1 for ln in rendered.splitlines() if ln.startswith("- ["))


def write_log(payload, source, resolved):
    script = Path(__file__).parent / "log-injection.sh"
    bash_cmd = f'bash "{script}" "$1" "$2" "$3" instinct-injections.jsonl'
    subprocess.run(["bash", "-c", bash_cmd, "_", json.dumps(payload),
                    json.dumps(resolved), source],
                   stderr=subprocess.DEVNULL, env=os.environ.copy(), check=False)
