"""Network + cache I/O for the gh-cache MCP server."""
import os
import urllib.error
import urllib.request
from pathlib import Path


def _api_base():
    return os.environ.get("_TEST_GH_API_BASE", "https://api.github.com")


def _open(url, accept, timeout=8):
    token = os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"]
    req = urllib.request.Request(
        url, headers={"Authorization": f"token {token}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch_pr_data(owner, repo, pr):
    if not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        return {"ok": False, "reason": "no token"}
    try:
        return _do_fetch(owner, repo, pr)
    except (TimeoutError, urllib.error.URLError) as exc:
        return {"ok": False, "reason": _classify(exc)}


def _do_fetch(owner, repo, pr):
    base = f"{_api_base()}/repos/{owner}/{repo}/pulls/{pr}"
    return {"ok": True,
            "view": _open(base, "application/vnd.github+json"),
            "diff": _open(base, "application/vnd.github.v3.diff"),
            "files": _open(f"{base}/files", "application/vnd.github+json")}


def _classify(exc):
    return "timeout" if isinstance(exc, TimeoutError) else "http error"


def write_cache(cache_dir, view, diff, files):
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    Path(cache_dir, "view.json").write_text(view)
    Path(cache_dir, "diff.patch").write_text(diff)
    Path(cache_dir, "files.txt").write_text(files)
    Path(cache_dir, ".complete").touch()
