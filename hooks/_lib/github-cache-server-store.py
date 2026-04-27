"""Cache filesystem writes for the gh-cache MCP server."""
import os
from pathlib import Path


def _atomic_write(target, content):
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def write_cache(cache_dir, view, diff, files):
    base = Path(cache_dir)
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(base, 0o700)
    _atomic_write(base / "view.json", view)
    _atomic_write(base / "diff.patch", diff)
    _atomic_write(base / "files.txt", files)
    (base / ".complete").touch(mode=0o600)
