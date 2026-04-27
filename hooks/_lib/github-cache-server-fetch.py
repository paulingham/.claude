"""Network + cache I/O for the gh-cache MCP server."""
import importlib.util
import os
import urllib.error
import urllib.request
from pathlib import Path

_API_BASE = "https://api.github.com"  # SSRF guard: no env override.
_JSON = "application/vnd.github+json"
_DIFF = "application/vnd.github.v3.diff"


_spec = importlib.util.spec_from_file_location(
    "_ghc_loader", Path(__file__).parent / "github-cache-server-loader.py")
_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_loader)
_shape = _loader.load_sibling("shape")
write_cache = _loader.load_sibling("store").write_cache


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
    base = f"{_API_BASE}/repos/{owner}/{repo}/pulls/{pr}"
    return {"ok": True,
            "view": _shape.reshape_view(_open(base, _JSON)),
            "diff": _open(base, _DIFF),
            "files": _shape.reshape_files(_open(f"{base}/files", _JSON))}


def _classify(exc):
    return "timeout" if isinstance(exc, TimeoutError) else "http error"
