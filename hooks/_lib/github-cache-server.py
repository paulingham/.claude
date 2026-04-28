"""Entry point: stdio JSON-RPC MCP server that prefetches GH PR data."""
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).parent


def _load(stem):
    path = _HERE / f"github-cache-server-{stem}.py"
    spec = importlib.util.spec_from_file_location(f"_ghc_{stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_lib = _load("lib")
_fetch = _load("fetch")
_prefetch = _load("prefetch")
_rpc = _load("rpc")
_dispatch = _rpc.make_dispatch(_lib, _fetch, _prefetch)


def _fetch_pr_data(owner, repo, pr):
    """Re-export for tests; production callers go via JSON-RPC tools/call."""
    return _fetch.fetch_pr_data(owner, repo, pr)


def serve(stdin, stdout):
    for line in stdin:
        _process_line(line, stdout)


def _process_line(line, stdout):
    text = line.strip()
    if not text:
        return
    response = _dispatch(json.loads(text))
    if response is not None:
        stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve(sys.stdin, sys.stdout)
