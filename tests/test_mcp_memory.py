"""MCP memory server unit tests (stdlib JSON-RPC over stdio)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))

from mcp_memory._lib import rpc, io_loop, tools  # noqa: E402


class TestRpcParseValid(unittest.TestCase):
    def test_parses_valid_request_line(self):
        line = '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}'
        msg = rpc.parse(line)
        self.assertEqual(msg["id"], 1)
        self.assertEqual(msg["method"], "ping")
        self.assertEqual(msg["params"], {})


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
        self.assertEqual(resp["jsonrpc"], "2.0")
        self.assertEqual(resp["id"], 3)
        self.assertEqual(resp["error"]["code"], -32602)
        self.assertEqual(resp["error"]["message"], "bad")
        self.assertNotIn("result", resp)


class TestInitialize(unittest.TestCase):
    def test_initialize_returns_protocol_info(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2024-11-05"}}
        resp = tools.dispatch(req)
        payload = resp["result"]
        self.assertEqual(payload["protocolVersion"], "2024-11-05")
        self.assertEqual(payload["capabilities"], {"tools": {}})
        self.assertEqual(payload["serverInfo"]["name"], "memory")
        self.assertIn("version", payload["serverInfo"])


class TestIoLoopDispatch(unittest.TestCase):
    def test_reads_line_dispatches_writes_response(self):
        stdin, stdout = _streams('{"jsonrpc":"2.0","id":1,"method":"ok"}\n')
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        line = stdout.getvalue().rstrip("\n")
        self.assertEqual(json.loads(line),
                         {"jsonrpc": "2.0", "id": 1, "result": {"ran": "ok"}})


class TestIoLoopParseError(unittest.TestCase):
    def test_bad_line_emits_parse_error(self):
        stdin, stdout = _streams("not json\n")
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        line = json.loads(stdout.getvalue().rstrip("\n"))
        self.assertEqual(line["error"]["code"], rpc.PARSE_ERROR)
        self.assertIsNone(line["id"])


class TestIoLoopEof(unittest.TestCase):
    def test_empty_stdin_exits_cleanly(self):
        stdin, stdout = _streams("")
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        self.assertEqual(stdout.getvalue(), "")


def _streams(text):
    import io
    return io.StringIO(text), io.StringIO()


def _canned_dispatcher(message):
    return rpc.result(message["id"], {"ran": message["method"]})


if __name__ == "__main__":
    unittest.main()
