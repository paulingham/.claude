"""Tests for mcp_memory._lib.tools — method dispatch."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from _support import build_populated_db  # noqa: E402
from mcp_memory._lib import tools  # noqa: E402


class TestInitialize(unittest.TestCase):
    def test_initialize_returns_protocol_info(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        resp = tools.dispatch(req)
        payload = resp["result"]
        self.assertEqual(payload["protocolVersion"], "2024-11-05")
        self.assertEqual(payload["capabilities"], {"tools": {}})
        self.assertEqual(payload["serverInfo"]["name"], "memory")
        self.assertIn("version", payload["serverInfo"])


class TestToolsList(unittest.TestCase):
    def test_lists_four_tools_with_schemas(self):
        resp = tools.dispatch({"id": 2, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(sorted(names), sorted([
            "search_memory", "get_timeline",
            "get_observations", "get_findings"]))

    def test_search_memory_schema_requires_query(self):
        resp = tools.dispatch({"id": 3, "method": "tools/list"})
        listed = {t["name"]: t for t in resp["result"]["tools"]}
        self.assertEqual(listed["search_memory"]["inputSchema"]["required"],
                         ["query"])
        self.assertIn("query",
                      listed["search_memory"]["inputSchema"]["properties"])


class TestUnknownMethod(unittest.TestCase):
    def test_unknown_method_returns_method_not_found(self):
        resp = tools.dispatch({"id": 9, "method": "bogus"})
        self.assertEqual(resp["error"]["code"], -32601)


class TestToolsCallInvalidParams(unittest.TestCase):
    def test_missing_query_maps_to_invalid_params(self):
        resp = tools.dispatch({"id": 10, "method": "tools/call",
                               "params": {"name": "search_memory",
                                          "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32602)

    def test_limit_zero_maps_to_invalid_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            resp = tools.dispatch({"id": 11, "method": "tools/call",
                                   "params": {"name": "search_memory",
                                              "arguments": {
                                                  "query": "x",
                                                  "limit": 0,
                                                  "db_path": str(db)}}})
        self.assertEqual(resp["error"]["code"], -32602)


class TestToolsCallUnknownTool(unittest.TestCase):
    def test_unknown_tool_returns_method_not_found(self):
        resp = tools.dispatch({"id": 12, "method": "tools/call",
                               "params": {"name": "nope", "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32601)


class TestToolsCallInternalError(unittest.TestCase):
    def test_unexpected_exception_maps_to_internal_error(self):
        from mcp_memory._lib import handlers
        original = handlers.search_memory
        handlers.search_memory = lambda _a: (_ for _ in ()).throw(
            RuntimeError("boom"))
        try:
            resp = tools.dispatch({"id": 13, "method": "tools/call",
                                   "params": {"name": "search_memory",
                                              "arguments": {"query": "x"}}})
        finally:
            handlers.search_memory = original
        self.assertEqual(resp["error"]["code"], -32603)
        self.assertNotIn("boom", resp["error"]["message"])


if __name__ == "__main__":
    unittest.main()
