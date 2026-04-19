"""Tests for mcp_memory._lib.io_loop — stdio framing."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _mcp_support import streams  # noqa: E402
from mcp_memory._lib import io_loop, rpc  # noqa: E402


class TestIoLoopDispatch(unittest.TestCase):
    def test_reads_line_dispatches_writes_response(self):
        stdin, stdout = streams('{"jsonrpc":"2.0","id":1,"method":"ok"}\n')
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        line = stdout.getvalue().rstrip("\n")
        self.assertEqual(json.loads(line),
                         {"jsonrpc": "2.0", "id": 1, "result": {"ran": "ok"}})


class TestIoLoopParseError(unittest.TestCase):
    def test_bad_line_emits_parse_error(self):
        stdin, stdout = streams("not json\n")
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        line = json.loads(stdout.getvalue().rstrip("\n"))
        self.assertEqual(line["error"]["code"], rpc.PARSE_ERROR)
        self.assertIsNone(line["id"])


class TestIoLoopEof(unittest.TestCase):
    def test_empty_stdin_exits_cleanly(self):
        stdin, stdout = streams("")
        io_loop.serve(stdin, stdout, _canned_dispatcher)
        self.assertEqual(stdout.getvalue(), "")


def _canned_dispatcher(message):
    return rpc.result(message["id"], {"ran": message["method"]})


if __name__ == "__main__":
    unittest.main()
