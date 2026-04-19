"""End-to-end: spawn server.py as subprocess, drive JSON-RPC, assert shape."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "skills" / "mcp_memory" / "server.py"


def _drive(input_text, timeout=5):
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
    return stdout, stderr


def _lines(input_requests):
    return "".join(json.dumps(r) + "\n" for r in input_requests)


class TestStdoutDiscipline(unittest.TestCase):
    def test_every_stdout_line_is_valid_jsonrpc(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            reqs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "search_memory",
                            "arguments": {"query": "Read",
                                          "db_path": str(db)}}}]
            stdout, _ = _drive(_lines(reqs))
            lines = [ln for ln in stdout.split("\n") if ln]
            self.assertEqual(len(lines), 3)
            for ln in lines:
                parsed = json.loads(ln)
                self.assertEqual(parsed["jsonrpc"], "2.0")
                self.assertIn("id", parsed)
                self.assertTrue("result" in parsed or "error" in parsed)


class TestInitializeE2E(unittest.TestCase):
    def test_initialize_returns_protocol_version(self):
        reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}]
        stdout, _ = _drive(_lines(reqs))
        resp = json.loads(stdout.strip())
        self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")


class TestBadLineDoesNotCrash(unittest.TestCase):
    def test_unparseable_line_returns_parse_error_and_continues(self):
        stdout, _ = _drive(
            "not-json\n"
            + json.dumps({"jsonrpc": "2.0", "id": 5,
                          "method": "initialize"}) + "\n")
        lines = [json.loads(ln) for ln in stdout.split("\n") if ln]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["error"]["code"], -32700)
        self.assertEqual(lines[1]["result"]["serverInfo"]["name"], "memory")


class TestDbMissingOnStderrOnly(unittest.TestCase):
    def test_warning_goes_to_stderr_not_stdout(self):
        reqs = [{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                 "params": {"name": "search_memory",
                            "arguments": {"query": "x",
                                          "db_path": "/tmp/nope_xyz.sqlite"}}}]
        stdout, stderr = _drive(_lines(reqs))
        for ln in stdout.split("\n"):
            if ln:
                json.loads(ln)
        self.assertIn("db missing", stderr)


if __name__ == "__main__":
    unittest.main()
