"""Server-module entrypoint tests (alias to the underscore-named test module).

The TDD guard maps source files like `github-cache-server.py` to a hyphenated
test path; the comprehensive test suite lives at `test_github_cache_server.py`
and pytest collects both.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "hooks" / "_lib" / "github-cache-server.py"


def _load_server():
    spec = importlib.util.spec_from_file_location("_ghc_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_ghc_server"] = module
    spec.loader.exec_module(module)
    return module


class _Resp:
    def __init__(self, body):
        self._body = body.encode("utf-8") if isinstance(body, str) else body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TestServeRoundtrip(unittest.TestCase):
    def setUp(self):
        os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"] = "t"
        os.environ["CLAUDE_SESSION_ID"] = "s"
        self.srv = _load_server()

    def test_initialize_emits_one_response(self):
        req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
        out = io.StringIO()
        self.srv.serve(io.StringIO(req), out)
        line = json.loads(out.getvalue().strip())
        self.assertEqual(line["result"]["serverInfo"]["name"], "gh-cache")

    def test_blank_lines_are_ignored(self):
        out = io.StringIO()
        self.srv.serve(io.StringIO("\n\n"), out)
        self.assertEqual(out.getvalue(), "")

    def test_prefetch_writes_cache_complete_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CLAUDE_GH_CACHE_DIR"] = tmp
            os.environ["_TEST_GH_OWNER_REPO"] = "o/r"
            with mock.patch("urllib.request.urlopen",
                            side_effect=lambda req, timeout=None: _Resp("{}")):
                req = json.dumps({"jsonrpc": "2.0", "id": 9,
                                  "method": "tools/call",
                                  "params": {"name": "prefetch_pr",
                                             "arguments": {"command": "gh pr merge 47"}}}) + "\n"
                out = io.StringIO()
                self.srv.serve(io.StringIO(req), out)
            self.assertTrue((Path(tmp) / "s-47" / ".complete").exists())


if __name__ == "__main__":
    unittest.main()
