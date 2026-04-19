"""Tests for mcp_memory._lib.rpc — JSON-RPC 2.0 builders."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from mcp_memory._lib import rpc  # noqa: E402


class TestRpcParseValid(unittest.TestCase):
    def test_parses_valid_request_line(self):
        line = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}'
        msg = rpc.parse(line)
        self.assertEqual(msg["id"], 1)
        self.assertEqual(msg["method"], "ping")


class TestRpcParseError(unittest.TestCase):
    def test_malformed_json_raises_parse_error(self):
        with self.assertRaises(rpc.ParseError):
            rpc.parse("not json")


class TestRpcResult(unittest.TestCase):
    def test_result_envelope_shape(self):
        resp = rpc.result(req_id=7, payload={"ok": True})
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 7)
        self.assertEqual(resp["result"], {"ok": True})
        self.assertNotIn("error", resp)


class TestRpcError(unittest.TestCase):
    def test_error_envelope_shape(self):
        resp = rpc.error(req_id=3, code=-32602, message="bad")
        self.assertEqual(resp["error"]["code"], -32602)
        self.assertEqual(resp["error"]["message"], "bad")
        self.assertNotIn("result", resp)


if __name__ == "__main__":
    unittest.main()
