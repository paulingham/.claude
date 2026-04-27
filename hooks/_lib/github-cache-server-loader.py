"""Sibling-module loader for the gh-cache MCP server."""
import importlib.util
from pathlib import Path

_HERE = Path(__file__).parent


def load_sibling(stem):
    spec = importlib.util.spec_from_file_location(
        f"_ghc_{stem}", _HERE / f"github-cache-server-{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
