"""Tests for mcp_memory._lib.call — tools/call routing + error mapping."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from mcp_memory._lib import call, handlers  # noqa: E402


class TestUnknownTool(unittest.TestCase):
    def test_unknown_tool_returns_method_not_found(self):
        resp = call.handle({"id": 1, "params": {"name": "nope",
                                                "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32601)


class TestInvalidParams(unittest.TestCase):
    def test_missing_required_arg_maps_to_invalid_params(self):
        resp = call.handle({"id": 2, "params": {"name": "search_memory",
                                                "arguments": {}}})
        self.assertEqual(resp["error"]["code"], -32602)


class TestInternalError(unittest.TestCase):
    def test_unexpected_exception_maps_to_internal_error(self):
        original = handlers.search_memory
        handlers.search_memory = lambda _a: (_ for _ in ()).throw(
            RuntimeError("boom"))
        try:
            resp = call.handle({"id": 3, "params": {
                "name": "search_memory",
                "arguments": {"query": "x"}}})
        finally:
            handlers.search_memory = original
        self.assertEqual(resp["error"]["code"], -32603)
        self.assertNotIn("boom", resp["error"]["message"])


class TestContentShape(unittest.TestCase):
    def test_success_returns_mcp_content_with_text_and_structured(self):
        resp = call.handle({"id": 4, "params": {
            "name": "search_memory",
            "arguments": {"query": "x", "db_path": "/tmp/nope.sqlite"}}})
        body = resp["result"]
        self.assertFalse(body["isError"])
        self.assertEqual(body["content"][0]["type"], "text")
        self.assertIn("tier", body["structuredContent"])


if __name__ == "__main__":
    unittest.main()
