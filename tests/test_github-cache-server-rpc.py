"""Tests for the JSON-RPC dispatch module."""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RPC_PATH = REPO / "hooks" / "_lib" / "github-cache-server-rpc.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _StubLib:
    @staticmethod
    def extract_pr_from_command(cmd):
        return None


class _StubFetch:
    pass


class _StubPrefetch:
    @staticmethod
    def prefetch(args, lib, fetch):
        return {"ok": False, "reason": "stub"}


class TestRpcDispatch(unittest.TestCase):
    def setUp(self):
        self.rpc = _load("gh_cache_rpc", RPC_PATH)
        self.dispatch = self.rpc.make_dispatch(_StubLib, _StubFetch, _StubPrefetch)

    def test_initialize_returns_protocol(self):
        resp = self.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(resp["result"]["serverInfo"]["name"], "gh-cache")

    def test_tools_list_exposes_prefetch_pr(self):
        resp = self.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("prefetch_pr", names)

    def test_tools_call_routes_to_prefetch(self):
        msg = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": "prefetch_pr", "arguments": {"command": "x"}}}
        resp = self.dispatch(msg)
        env = resp["result"]["structuredContent"]
        self.assertEqual(env["reason"], "stub")

    def test_unknown_method_returns_none(self):
        self.assertIsNone(self.dispatch({"jsonrpc": "2.0", "id": 4, "method": "x"}))


if __name__ == "__main__":
    unittest.main()
