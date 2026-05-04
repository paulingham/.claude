"""LSP-as-MCP bridge — Path-B advisory stub for mcp_lsp_diagnostics_{ts,py}.

Real LSP shell-out deferred; only this file changes when wired. See
rules/_detail/agent-protocol.md § Per-Agent Tool Scoping for contract.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_rpc():
    path = Path(__file__).parent / "lsp-bridge-rpc.py"
    spec = importlib.util.spec_from_file_location("_lsp_rpc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _emit(reply):
    sys.stdout.write(json.dumps(reply) + "\n")
    sys.stdout.flush()


def _loop(lang, rpc):
    for line in sys.stdin:
        reply = rpc.route(json.loads(line), lang)
        if reply is not None:
            _emit(reply)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, choices=["ts", "py"])
    _loop(parser.parse_args().language, _load_rpc())


if __name__ == "__main__":
    main()
