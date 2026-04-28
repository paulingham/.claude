"""Tests for the prefetch tool: extract → resolve → fetch → cache."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PATHS = {
    "lib": REPO / "hooks" / "_lib" / "github-cache-server-lib.py",
    "prefetch": REPO / "hooks" / "_lib" / "github-cache-server-prefetch.py",
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _FakeFetch:
    def __init__(self, response):
        self._response = response
        self.written = []

    def fetch_pr_data(self, owner, repo, pr):
        return self._response

    def write_cache(self, cache_dir, view, diff, files):
        self.written.append((cache_dir, view, diff, files))


class TestPrefetch(unittest.TestCase):
    def setUp(self):
        self.lib = _load("gh_cache_lib_p", PATHS["lib"])
        self.pre = _load("gh_cache_pre", PATHS["prefetch"])
        os.environ["_TEST_GH_OWNER_REPO"] = "o/r"
        os.environ["CLAUDE_SESSION_ID"] = "sess"

    def tearDown(self):
        os.environ.pop("_TEST_GH_OWNER_REPO", None)
        os.environ.pop("CLAUDE_GH_CACHE_DIR", None)

    def test_no_pr_number(self):
        result = self.pre.prefetch({"command": "gh repo view"}, self.lib, _FakeFetch({}))
        self.assertEqual(result["reason"], "no PR number in command")

    def test_unsupported_remote_when_override_unset(self):
        os.environ.pop("_TEST_GH_OWNER_REPO", None)
        # git remote will fail or return non-github → unsupported
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = self.pre.prefetch({"command": "gh pr merge 5"},
                                           self.lib, _FakeFetch({}))
            finally:
                os.chdir(cwd)
        self.assertEqual(result["reason"], "unsupported remote")

    def test_fetch_failure_propagates(self):
        fake = _FakeFetch({"ok": False, "reason": "no token"})
        result = self.pre.prefetch({"command": "gh pr merge 5"}, self.lib, fake)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no token")

    def test_success_writes_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CLAUDE_GH_CACHE_DIR"] = tmp
            fake = _FakeFetch({"ok": True, "view": "v", "diff": "d", "files": "f"})
            result = self.pre.prefetch({"command": "gh pr merge 7"}, self.lib, fake)
            self.assertTrue(result["ok"])
            self.assertTrue(result["cache_dir"].endswith("sess-7"))
            self.assertEqual(len(fake.written), 1)


if __name__ == "__main__":
    unittest.main()
