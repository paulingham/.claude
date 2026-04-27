"""Cache filesystem writes for the gh-cache MCP server."""
from pathlib import Path


def write_cache(cache_dir, view, diff, files):
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(cache_dir, "view.json").write_text(view)
    Path(cache_dir, "diff.patch").write_text(diff)
    Path(cache_dir, "files.txt").write_text(files)
    Path(cache_dir, ".complete").touch()
